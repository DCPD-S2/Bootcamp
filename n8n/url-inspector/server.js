const express = require('express');
const { chromium } = require('playwright');
const dns = require('node:dns').promises;
const tls = require('node:tls');
const ipaddr = require('ipaddr.js');

const app = express();

app.disable('x-powered-by');
app.use(express.json({ limit: '50kb' }));

const PORT = Number(process.env.PORT || 8080);

const NAVIGATION_TIMEOUT_MS = Number(
  process.env.NAVIGATION_TIMEOUT_MS || 60000
);

const DNS_RETRIES = Number(
  process.env.DNS_RETRIES || 4
);

const MAX_REDIRECTS = Number(
  process.env.MAX_REDIRECTS || 5
);

const MAX_TEXT_LENGTH = Number(
  process.env.MAX_TEXT_LENGTH || 15000
);

const LAB_ALLOWED_HOSTS = new Set(
  String(process.env.LAB_ALLOW_HOSTS || '')
    .split(',')
    .map((host) => normalizeHostname(host))
    .filter(Boolean)
);

const BLOCKED_HOSTNAMES = new Set([
  'localhost',
  'localhost.localdomain',
  'metadata.google.internal'
]);

let browser;


/* =========================================================
   FUNCȚII GENERALE
========================================================= */

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}


function normalizeHostname(hostname) {
  return String(hostname || '')
    .trim()
    .toLowerCase()
    .replace(/^\[/, '')
    .replace(/\]$/, '')
    .replace(/\.$/, '');
}


function unique(values) {
  return [...new Set(values.filter(Boolean))];
}


function serializeError(error) {
  return {
    message: error?.message || String(error),
    code: error?.code || error?.cause?.code || null,
    name: error?.name || 'Error'
  };
}


/* =========================================================
   VERIFICARE IP ȘI DNS
========================================================= */

function isPublicIp(address) {
  try {
    let parsed = ipaddr.parse(address);

    if (
      parsed.kind() === 'ipv6' &&
      parsed.isIPv4MappedAddress()
    ) {
      parsed = parsed.toIPv4Address();
    }

    return parsed.range() === 'unicast';
  } catch {
    return false;
  }
}


async function resolveHostname(hostname) {
  const normalized = normalizeHostname(hostname);

  let lastError;

  for (
    let attempt = 1;
    attempt <= DNS_RETRIES;
    attempt += 1
  ) {
    try {
      const addresses = await dns.lookup(normalized, {
        all: true,
        verbatim: true
      });

      if (addresses.length > 0) {
        return addresses;
      }
    } catch (error) {
      lastError = error;
    }

    if (attempt < DNS_RETRIES) {
      await sleep(attempt * 750);
    }
  }

  const error = new Error(
    `DNS resolution failed for ${normalized}: ${
      lastError?.code ||
      lastError?.message ||
      'NO_ADDRESS'
    }`
  );

  error.code =
    lastError?.code ||
    'DNS_RESOLUTION_FAILED';

  throw error;
}


async function hostnameIsAllowed(hostname) {
  const normalized = normalizeHostname(hostname);

  if (
    !normalized ||
    BLOCKED_HOSTNAMES.has(normalized)
  ) {
    return false;
  }

  /*
   * Excepție pentru containerele locale de laborator.
   * Exemplu:
   * LAB_ALLOW_HOSTS=phishing-sim,collector
   */
  if (LAB_ALLOWED_HOSTS.has(normalized)) {
    return true;
  }

  /*
   * Dacă hostname-ul este direct o adresă IP,
   * îl verificăm fără DNS.
   */
  if (ipaddr.isValid(normalized)) {
    return isPublicIp(normalized);
  }

  const addresses = await resolveHostname(normalized);

  /*
   * Toate adresele DNS trebuie să fie publice.
   * Dacă una indică spre o adresă internă, blocăm cererea.
   */
  return addresses.every(({ address }) =>
    isPublicIp(address)
  );
}


/* =========================================================
   VALIDARE URL
========================================================= */

async function validateUrl(rawUrl) {
  let parsed;

  try {
    parsed = new URL(
      String(rawUrl || '').trim()
    );
  } catch {
    const error = new Error('URL invalid');
    error.code = 'INVALID_URL';
    throw error;
  }

  if (
    !['http:', 'https:'].includes(parsed.protocol)
  ) {
    const error = new Error(
      'Sunt permise numai URL-uri HTTP și HTTPS'
    );

    error.code = 'UNSUPPORTED_PROTOCOL';

    throw error;
  }

  if (parsed.username || parsed.password) {
    const error = new Error(
      'URL-urile care conțin credențiale sunt blocate'
    );

    error.code =
      'EMBEDDED_CREDENTIALS_BLOCKED';

    throw error;
  }

  if (
    !(await hostnameIsAllowed(parsed.hostname))
  ) {
    const error = new Error(
      'Domeniul indică o adresă locală, privată sau rezervată'
    );

    error.code =
      'PRIVATE_OR_RESERVED_DESTINATION';

    throw error;
  }

  return parsed;
}


/* =========================================================
   REDIRECTĂRI
========================================================= */

function countRedirects(request) {
  let count = 0;

  let current =
    request?.redirectedFrom?.() || null;

  while (current) {
    count += 1;
    current = current.redirectedFrom();
  }

  return count;
}


function redirectChain(request) {
  const urls = [];

  let current = request;

  while (current) {
    urls.unshift(current.url());
    current = current.redirectedFrom();
  }

  return unique(urls);
}


/* =========================================================
   VERIFICARE CERTIFICAT TLS
========================================================= */

async function inspectTlsCertificate(parsedUrl) {
  if (parsedUrl.protocol !== 'https:') {
    return {
      checked: false,
      valid: null,
      error: null,
      subject: null,
      issuer: null,
      valid_from: null,
      valid_to: null,
      fingerprint256: null
    };
  }

  return new Promise((resolve) => {
    let settled = false;

    const finish = (result, socket) => {
      if (settled) {
        return;
      }

      settled = true;

      socket?.destroy();

      resolve(result);
    };

    const hostname =
      normalizeHostname(parsedUrl.hostname);

    const socket = tls.connect({
      host: hostname,
      port: Number(parsedUrl.port || 443),
      servername: hostname,

      /*
       * Permitem conexiunea pentru a putea citi
       * certificatul, dar păstrăm rezultatul validării.
       */
      rejectUnauthorized: false
    });

    socket.setTimeout(8000);

    socket.once('secureConnect', () => {
      const certificate =
        socket.getPeerCertificate();

      finish(
        {
          checked: true,
          valid: socket.authorized,
          error:
            socket.authorizationError || null,

          subject:
            certificate?.subject || null,

          issuer:
            certificate?.issuer || null,

          valid_from:
            certificate?.valid_from || null,

          valid_to:
            certificate?.valid_to || null,

          fingerprint256:
            certificate?.fingerprint256 || null
        },
        socket
      );
    });

    socket.once('timeout', () => {
      finish(
        {
          checked: true,
          valid: false,
          error: 'TLS_TIMEOUT',
          subject: null,
          issuer: null,
          valid_from: null,
          valid_to: null,
          fingerprint256: null
        },
        socket
      );
    });

    socket.once('error', (error) => {
      finish(
        {
          checked: true,
          valid: false,
          error:
            error.code ||
            error.message,

          subject: null,
          issuer: null,
          valid_from: null,
          valid_to: null,
          fingerprint256: null
        },
        socket
      );
    });
  });
}


/* =========================================================
   PAGINI OFICIALE DE TEST
========================================================= */

function isKnownSafeTestPage(parsedUrl) {
  const hostname =
    normalizeHostname(parsedUrl.hostname);

  const pathname =
    parsedUrl.pathname.replace(/\/+$/, '/') || '/';

  const knownPages = [
    {
      hostname: 'www.amtso.org',
      pathname:
        '/check-desktop-phishing-page/'
    },
    {
      hostname: 'www.amtso.org',
      pathname:
        '/feature-settings-check-phishing-page/'
    },
    {
      hostname: 'www.amtso.org',
      pathname:
        '/feature-settings-check-drive-by-download/'
    },
    {
      hostname:
        'testsafebrowsing.appspot.com',
      pathname: '/s/phishing.html'
    }
  ];

  return knownPages.some(
    (page) =>
      page.hostname === hostname &&
      page.pathname === pathname
  );
}


/* =========================================================
   CLASIFICARE DETERMINISTĂ
========================================================= */

function classifyInspection({
  safeTestPage,
  credentialExfiltrationPattern,
  downloadAttempted,
  tlsInvalid,
  deterministicScore,
  navigationTimedOut,
  hasPageEvidence
}) {
  if (safeTestPage) {
    return {
      classification: 'SAFE_TEST_PAGE',

      operationalRiskScore:
        Math.min(deterministicScore, 10),

      simulatedBehavior:
        downloadAttempted ||
        credentialExfiltrationPattern
          ? 'HARMFUL'
          : 'PHISHING_TEST'
    };
  }

  if (
    credentialExfiltrationPattern ||
    downloadAttempted
  ) {
    return {
      classification: 'HARMFUL',

      operationalRiskScore:
        Math.max(deterministicScore, 75),

      simulatedBehavior: 'NONE'
    };
  }

  if (
    navigationTimedOut &&
    !hasPageEvidence
  ) {
    return {
      classification:
        'INSUFFICIENT_DATA',

      operationalRiskScore:
        deterministicScore,

      simulatedBehavior: 'NONE'
    };
  }

  if (
    tlsInvalid ||
    deterministicScore >= 30
  ) {
    return {
      classification: 'SUSPICIOUS',

      operationalRiskScore:
        Math.max(
          deterministicScore,
          tlsInvalid ? 30 : 0
        ),

      simulatedBehavior: 'NONE'
    };
  }

  return {
    classification: 'HARMLESS',

    operationalRiskScore:
      deterministicScore,

    simulatedBehavior: 'NONE'
  };
}


/* =========================================================
   HEALTH CHECK
========================================================= */

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    browser_ready: Boolean(browser)
  });
});


/* =========================================================
   ENDPOINT PRINCIPAL
========================================================= */

app.post('/check', async (req, res) => {
  const rawUrl = String(
    req.body?.url || ''
  ).trim();

  let context;

  try {
    const initialUrl =
      await validateUrl(rawUrl);

    const initialTls =
      await inspectTlsCertificate(initialUrl);

    context = await browser.newContext({
      acceptDownloads: false,
      serviceWorkers: 'block',

      /*
       * Chromium continuă încărcarea chiar dacă
       * certificatul este invalid.
       * Problema TLS este păstrată separat în raport.
       */
      ignoreHTTPSErrors: true,

      viewport: {
        width: 1280,
        height: 720
      }
    });

    const contactedDomains = new Set();

    const blockedRequestDetails = [];

    const navigationHistory = [];

    let downloadAttempted = false;
    let blockedRequests = 0;


    /* -----------------------------------------------------
       INTERCEPTAREA CERERILOR
    ----------------------------------------------------- */

    await context.route(
      '**/*',
      async (route) => {
        const request = route.request();

        try {
          const target =
            new URL(request.url());

          if (
            !['http:', 'https:'].includes(
              target.protocol
            )
          ) {
            blockedRequests += 1;

            blockedRequestDetails.push({
              url: request.url(),
              reason:
                'unsupported_protocol'
            });

            return route.abort();
          }

          if (
            countRedirects(request) >
            MAX_REDIRECTS
          ) {
            blockedRequests += 1;

            blockedRequestDetails.push({
              url: request.url(),
              reason:
                'too_many_redirects'
            });

            return route.abort();
          }

          /*
           * Protecție SSRF pentru fiecare cerere
           * și fiecare redirect.
           */
          if (
            !(await hostnameIsAllowed(
              target.hostname
            ))
          ) {
            blockedRequests += 1;

            blockedRequestDetails.push({
              url: request.url(),
              reason:
                'private_or_reserved_destination'
            });

            return route.abort();
          }

          contactedDomains.add(
            normalizeHostname(
              target.hostname
            )
          );

          /*
           * Eliminăm datele sensibile.
           */
          const headers = {
            ...request.headers()
          };

          delete headers.cookie;
          delete headers.authorization;
          delete headers[
            'proxy-authorization'
          ];

          /*
           * Nu avem nevoie de media sau fonturi
           * pentru analiză.
           */
          if (
            ['media', 'font'].includes(
              request.resourceType()
            )
          ) {
            return route.abort();
          }

          return route.continue({
            headers
          });
        } catch (error) {
          blockedRequests += 1;

          blockedRequestDetails.push({
            url: request.url(),

            reason:
              error.code ||
              error.message ||
              'route_validation_failed'
          });

          return route.abort();
        }
      }
    );


    /* -----------------------------------------------------
       PAGINA PLAYWRIGHT
    ----------------------------------------------------- */

    const page =
      await context.newPage();

    page.setDefaultNavigationTimeout(
      NAVIGATION_TIMEOUT_MS
    );

    page.setDefaultTimeout(
      NAVIGATION_TIMEOUT_MS
    );


    /* Detectare download */

    page.on(
      'download',
      async (download) => {
        downloadAttempted = true;

        await download
          .cancel()
          .catch(() => {});
      }
    );


    /* Închidere dialoguri JavaScript */

    page.on(
      'dialog',
      async (dialog) => {
        await dialog
          .dismiss()
          .catch(() => {});
      }
    );


    /* Istoricul navigării */

    page.on(
      'framenavigated',
      (frame) => {
        if (frame === page.mainFrame()) {
          const url = frame.url();

          if (
            url &&
            url !== 'about:blank'
          ) {
            navigationHistory.push(url);
          }
        }
      }
    );


    /* -----------------------------------------------------
       NAVIGARE
    ----------------------------------------------------- */

    let response = null;

    let navigationTimedOut = false;

    try {
      response = await page.goto(
        initialUrl.toString(),
        {
          waitUntil: 'domcontentloaded',

          timeout:
            NAVIGATION_TIMEOUT_MS
        }
      );
    } catch (error) {
      if (
        error.name === 'TimeoutError'
      ) {
        navigationTimedOut = true;

        /*
         * Pagina poate fi parțial încărcată
         * și totuși analizabilă.
         */
        await page
          .waitForLoadState(
            'domcontentloaded',
            {
              timeout: 5000
            }
          )
          .catch(() => {});
      } else {
        throw error;
      }
    }

    await page.waitForTimeout(1000);


    /* -----------------------------------------------------
       URL FINAL
    ----------------------------------------------------- */

    const currentUrl = page.url();

    const finalUrl =
      currentUrl.startsWith('http://') ||
      currentUrl.startsWith('https://')
        ? currentUrl
        : initialUrl.toString();

    const finalParsed =
      await validateUrl(finalUrl);

    const finalTls =
      finalParsed.origin ===
      initialUrl.origin
        ? initialTls
        : await inspectTlsCertificate(
            finalParsed
          );


    /* -----------------------------------------------------
       EXTRAGERE CONȚINUT
    ----------------------------------------------------- */

    const title =
      await page
        .title()
        .catch(() => '');

    const pageData =
      await page
        .evaluate(
          (maxTextLength) => {
            const bodyText =
              document.body?.innerText || '';

            const forms = [
              ...document.forms
            ].map((form) => {
              const inputs = [
                ...form.querySelectorAll(
                  'input'
                )
              ];

              return {
                method:
                  (
                    form.method || 'get'
                  ).toLowerCase(),

                action:
                  form.action || '',

                passwordFields:
                  inputs.filter(
                    (input) =>
                      input.type
                        .toLowerCase() ===
                      'password'
                  ).length,

                emailFields:
                  inputs.filter(
                    (input) =>
                      input.type
                        .toLowerCase() ===
                      'email'
                  ).length,

                fileFields:
                  inputs.filter(
                    (input) =>
                      input.type
                        .toLowerCase() ===
                      'file'
                  ).length,

                hiddenFields:
                  inputs.filter(
                    (input) =>
                      input.type
                        .toLowerCase() ===
                      'hidden'
                  ).length
              };
            });

            const metaRefresh =
              document
                .querySelector(
                  'meta[http-equiv="refresh" i]'
                )
                ?.getAttribute(
                  'content'
                ) || '';

            return {
              text:
                bodyText.slice(
                  0,
                  maxTextLength
                ),

              forms,

              iframeCount:
                document.querySelectorAll(
                  'iframe'
                ).length,

              linkCount:
                document.querySelectorAll(
                  'a[href]'
                ).length,

              metaRefresh
            };
          },

          MAX_TEXT_LENGTH
        )
        .catch(() => ({
          text: '',
          forms: [],
          iframeCount: 0,
          linkCount: 0,
          metaRefresh: ''
        }));


    /* -----------------------------------------------------
       REDIRECTĂRI
    ----------------------------------------------------- */

    const redirects = response
      ? redirectChain(
          response.request()
        )
      : unique([
          initialUrl.toString(),
          ...navigationHistory,
          finalUrl
        ]);

    const originalDomain =
      normalizeHostname(
        initialUrl.hostname
      );

    const finalDomain =
      normalizeHostname(
        finalParsed.hostname
      );


    /* -----------------------------------------------------
       CALCULARE SCOR
    ----------------------------------------------------- */

    const findings = [];

    let deterministicScore = 0;


    /* HTTP fără TLS */

    if (
      initialUrl.protocol === 'http:'
    ) {
      findings.push(
        'Pagina inițială folosește HTTP, nu HTTPS'
      );

      deterministicScore += 15;
    }


    /* Certificat inițial invalid */

    if (
      initialTls.checked &&
      initialTls.valid === false
    ) {
      findings.push(
        `Certificatul TLS inițial nu este valid: ${
          initialTls.error ||
          'eroare necunoscută'
        }`
      );

      deterministicScore += 30;
    }


    /* Certificat final invalid */

    if (
      finalTls.checked &&
      finalTls.valid === false &&
      (
        finalParsed.origin !==
          initialUrl.origin ||
        initialTls.valid !== false
      )
    ) {
      findings.push(
        `Certificatul TLS final nu este valid: ${
          finalTls.error ||
          'eroare necunoscută'
        }`
      );

      deterministicScore += 30;
    }


    /* Redirect către alt hostname */

    if (
      originalDomain !== finalDomain
    ) {
      findings.push(
        `Pagina redirecționează către alt hostname: ${finalDomain}`
      );

      deterministicScore += 15;
    }


    /* Lanț mare de redirectări */

    if (
      redirects.length - 1 > 3
    ) {
      findings.push(
        'Există mai multe redirecționări'
      );

      deterministicScore += 10;
    }


    /* Meta refresh */

    if (pageData.metaRefresh) {
      findings.push(
        'Pagina conține o redirecționare de tip meta refresh'
      );

      deterministicScore += 10;
    }


    /* Câmpuri de parolă */

    const passwordFields =
      pageData.forms.reduce(
        (sum, form) =>
          sum + form.passwordFields,

        0
      );

    if (passwordFields > 0) {
      findings.push(
        'Pagina solicită introducerea unei parole'
      );

      deterministicScore += 10;
    }


    /* -----------------------------------------------------
       ANALIZA FORMULARELOR
    ----------------------------------------------------- */

    let credentialExfiltrationPattern =
      false;

    for (
      const form of pageData.forms
    ) {
      if (!form.action) {
        continue;
      }

      try {
        const actionUrl = new URL(
          form.action,
          finalUrl
        );

        const actionDomain =
          normalizeHostname(
            actionUrl.hostname
          );

        const sendsToDifferentHostname =
          actionDomain !== finalDomain;

        const downgradesToHttp =
          finalParsed.protocol ===
            'https:' &&
          actionUrl.protocol === 'http:';


        /*
         * Parola este trimisă către alt hostname.
         */
        if (
          form.passwordFields > 0 &&
          sendsToDifferentHostname
        ) {
          credentialExfiltrationPattern =
            true;

          findings.push(
            `Formularul cu parolă trimite date către alt hostname: ${actionDomain}`
          );

          deterministicScore += 60;
        } else if (
          sendsToDifferentHostname
        ) {
          findings.push(
            `Un formular trimite date către alt hostname: ${actionDomain}`
          );

          deterministicScore += 20;
        }


        /*
         * Pagina HTTPS trimite formularul prin HTTP.
         */
        if (downgradesToHttp) {
          findings.push(
            'Un formular de pe o pagină HTTPS trimite date prin HTTP'
          );

          deterministicScore += 25;
        }
      } catch {
        findings.push(
          'Acțiunea unui formular nu a putut fi interpretată'
        );

        deterministicScore += 5;
      }
    }


    /* Download automat */

    if (downloadAttempted) {
      findings.push(
        'Pagina a încercat să inițieze o descărcare'
      );

      deterministicScore += 35;
    }


    /* Acces către destinații blocate */

    if (blockedRequests > 0) {
      findings.push(
        `${blockedRequests} cereri către destinații nepermise au fost blocate`
      );

      deterministicScore += 25;
    }


    deterministicScore =
      Math.min(
        deterministicScore,
        100
      );


    /* -----------------------------------------------------
       CLASIFICAREA FINALĂ
    ----------------------------------------------------- */

    const safeTestPage =
      isKnownSafeTestPage(
        finalParsed
      );

    const tlsInvalid =
      (
        initialTls.checked &&
        initialTls.valid === false
      ) ||
      (
        finalTls.checked &&
        finalTls.valid === false
      );

    const hasPageEvidence =
      Boolean(
        response ||
        title ||
        pageData.text ||
        pageData.forms.length > 0
      );

    const decision =
      classifyInspection({
        safeTestPage,
        credentialExfiltrationPattern,
        downloadAttempted,
        tlsInvalid,
        deterministicScore,
        navigationTimedOut,
        hasPageEvidence
      });


    /* -----------------------------------------------------
       LIMITĂRI
    ----------------------------------------------------- */

    const limitations = [
      'Lipsa indicatorilor vizibili nu garantează că pagina este legitimă',

      'Nu au fost utilizate baze externe de reputație',

      'Pagina a fost accesată fără cont, cookie-uri sau autentificare',

      'Compararea hostname-urilor formularelor poate produce rezultate fals pozitive pentru servicii legitime care folosesc domenii de autentificare separate',

      ...(
        navigationTimedOut
          ? [
              'Încărcarea paginii a depășit timpul disponibil'
            ]
          : []
      ),

      ...(
        safeTestPage
          ? [
              'Pagina este o pagină oficială de test și simulează un comportament de securitate'
            ]
          : []
      )
    ];


    /* -----------------------------------------------------
       RĂSPUNS
    ----------------------------------------------------- */

    res.status(200).json({
      requested_url:
        initialUrl.toString(),

      final_url: finalUrl,

      original_domain:
        originalDomain,

      final_domain:
        finalDomain,

      status_code:
        response?.status() || null,

      page_title: title,

      redirects,

      visible_text:
        pageData.text,

      forms:
        pageData.forms,

      password_fields:
        passwordFields,

      iframe_count:
        pageData.iframeCount,

      link_count:
        pageData.linkCount,

      meta_refresh:
        pageData.metaRefresh,

      contacted_domains:
        [...contactedDomains],

      download_attempted:
        downloadAttempted,

      blocked_requests:
        blockedRequests,

      blocked_request_details:
        blockedRequestDetails,

      credential_exfiltration_pattern:
        credentialExfiltrationPattern,

      tls: {
        initial: initialTls,
        final: finalTls
      },

      safe_test_page:
        safeTestPage,

      deterministic_score:
        deterministicScore,

      operational_risk_score:
        Math.min(
          decision.operationalRiskScore,
          100
        ),

      classification:
        decision.classification,

      simulated_behavior:
        decision.simulatedBehavior,

      findings:
        unique(findings),

      navigation_timed_out:
        navigationTimedOut,

      inspection_completed: true,

      limitations
    });
  } catch (error) {
    const details =
      serializeError(error);

    /*
     * Returnăm HTTP 200 pentru ca tool-ul n8n
     * să poată analiza eroarea.
     */
    res.status(200).json({
      requested_url: rawUrl,

      inspection_completed: false,

      classification:
        'INSUFFICIENT_DATA',

      operational_risk_score: 0,

      error:
        details.message,

      error_code:
        details.code,

      error_name:
        details.name,

      findings: [],

      limitations: [
        'Pagina nu a putut fi analizată complet',

        'Eroarea nu demonstrează că pagina este sigură sau periculoasă'
      ]
    });
  } finally {
    if (context) {
      await context
        .close()
        .catch(() => {});
    }
  }
});


/* =========================================================
   PORNIRE SERVER
========================================================= */

async function start() {
  browser = await chromium.launch({
    headless: true,

    args: [
      '--disable-dev-shm-usage'
    ]
  });

  app.listen(
    PORT,
    '0.0.0.0',
    () => {
      console.log(
        `URL Inspector rulează pe portul ${PORT}`
      );
    }
  );
}


/* =========================================================
   OPRIRE CONTROLATĂ
========================================================= */

async function shutdown(signal) {
  console.log(
    `Primit ${signal}. Oprire URL Inspector...`
  );

  await browser
    ?.close()
    .catch(() => {});

  process.exit(0);
}


process.on(
  'SIGTERM',
  () => shutdown('SIGTERM')
);

process.on(
  'SIGINT',
  () => shutdown('SIGINT')
);


start().catch((error) => {
  console.error(
    'URL Inspector nu a putut porni:',
    error
  );

  process.exit(1);
});