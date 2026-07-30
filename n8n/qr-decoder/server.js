'use strict';

const express = require('express');
const multer = require('multer');
const sharp = require('sharp');
const jsQR = require('jsqr');

const app = express();

const PORT = Number(process.env.PORT || 8082);

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const MAX_IMAGE_PIXELS = 30_000_000;
const MAX_CODES_PER_REGION = 4;

const TILE_GRIDS = [2, 3, 4];
const TILE_OVERLAP_RATIO = 0.22;

const ALLOWED_MIME_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp'
]);

app.disable('x-powered-by');

const upload = multer({
  storage: multer.memoryStorage(),

  limits: {
    fileSize: MAX_FILE_SIZE,
    files: 1
  },

  fileFilter: (_req, file, callback) => {
    if (!ALLOWED_MIME_TYPES.has(file.mimetype)) {
      return callback(
        new Error(
          `Tip de fișier neacceptat: ${file.mimetype}. ` +
          'Sunt permise PNG, JPEG și WebP.'
        )
      );
    }

    callback(null, true);
  }
});

function classifyPayload(payload) {
  const value = String(payload || '').trim();
  const lower = value.toLowerCase();

  if (
    lower.startsWith('http://') ||
    lower.startsWith('https://')
  ) {
    try {
      const parsed = new URL(value);

      return {
        payload_type: 'URL',
        scheme: parsed.protocol.replace(':', ''),
        hostname: parsed.hostname,
        port: parsed.port || null,
        host: parsed.host,
        should_execute: false,
        risk_level: 'unknown'
      };
    } catch {
      return {
        payload_type: 'INVALID_URL',
        should_execute: false,
        risk_level: 'suspicious'
      };
    }
  }

  if (lower.startsWith('wifi:')) {
    return {
      payload_type: 'WIFI',
      should_execute: false,
      risk_level: 'unknown'
    };
  }

  if (lower.startsWith('mailto:')) {
    return {
      payload_type: 'EMAIL_ACTION',
      should_execute: false,
      risk_level: 'unknown'
    };
  }

  if (
    lower.startsWith('tel:') ||
    lower.startsWith('sms:')
  ) {
    return {
      payload_type: 'PHONE_ACTION',
      should_execute: false,
      risk_level: 'unknown'
    };
  }

  if (
    lower.startsWith('bitcoin:') ||
    lower.startsWith('ethereum:')
  ) {
    return {
      payload_type: 'PAYMENT_REQUEST',
      should_execute: false,
      risk_level: 'suspicious'
    };
  }

  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('file:') ||
    lower.startsWith('data:') ||
    lower.startsWith('intent:')
  ) {
    return {
      payload_type: 'BLOCKED_SCHEME',
      scheme: value.split(':', 1)[0].toLowerCase(),
      should_execute: false,
      risk_level: 'high'
    };
  }

  return {
    payload_type: 'TEXT',
    should_execute: false,
    risk_level: 'unknown'
  };
}

async function normalizeSourceImage(buffer) {
  const result = await sharp(buffer)
    .rotate()
    .flatten({
      background: '#ffffff'
    })
    .toColourspace('srgb')
    .png()
    .toBuffer({
      resolveWithObject: true
    });

  const {
    width,
    height
  } = result.info;

  if (!width || !height) {
    throw new Error(
      'Nu au putut fi determinate dimensiunile imaginii'
    );
  }

  if (width * height > MAX_IMAGE_PIXELS) {
    throw new Error(
      `Imaginea este prea mare: ${width}x${height}`
    );
  }

  return {
    buffer: result.data,
    width,
    height
  };
}

function createSearchRegions(width, height) {
  const regions = [
    {
      name: 'full',
      left: 0,
      top: 0,
      width,
      height
    }
  ];

  for (const gridSize of TILE_GRIDS) {
    if (
      width < gridSize * 120 ||
      height < gridSize * 120
    ) {
      continue;
    }

    const cellWidth = Math.ceil(
      width / gridSize
    );

    const cellHeight = Math.ceil(
      height / gridSize
    );

    const overlapX = Math.max(
      40,
      Math.round(
        cellWidth * TILE_OVERLAP_RATIO
      )
    );

    const overlapY = Math.max(
      40,
      Math.round(
        cellHeight * TILE_OVERLAP_RATIO
      )
    );

    for (
      let row = 0;
      row < gridSize;
      row++
    ) {
      for (
        let column = 0;
        column < gridSize;
        column++
      ) {
        const baseLeft =
          column * cellWidth;

        const baseTop =
          row * cellHeight;

        const baseRight = Math.min(
          width,
          (column + 1) * cellWidth
        );

        const baseBottom = Math.min(
          height,
          (row + 1) * cellHeight
        );

        const left = Math.max(
          0,
          baseLeft - overlapX
        );

        const top = Math.max(
          0,
          baseTop - overlapY
        );

        const right = Math.min(
          width,
          baseRight + overlapX
        );

        const bottom = Math.min(
          height,
          baseBottom + overlapY
        );

        const regionWidth =
          right - left;

        const regionHeight =
          bottom - top;

        if (
          regionWidth <= 0 ||
          regionHeight <= 0
        ) {
          continue;
        }

        regions.push({
          name:
            `grid_${gridSize}_` +
            `r${row}_c${column}`,

          left,
          top,
          width: regionWidth,
          height: regionHeight
        });
      }
    }
  }

  return regions;
}

async function prepareRegion(
  sourceBuffer,
  region,
  mode
) {
  let pipeline = sharp(sourceBuffer)
    .extract({
      left: region.left,
      top: region.top,
      width: region.width,
      height: region.height
    });

  switch (mode) {
    case 'normal':
      break;

    case 'enhanced':
      pipeline = pipeline
        .normalize()
        .sharpen({
          sigma: 1
        });
      break;

    case 'threshold':
      pipeline = pipeline
        .greyscale()
        .normalize()
        .threshold(150)
        .toColourspace('srgb');
      break;

    default:
      throw new Error(
        `Mod necunoscut: ${mode}`
      );
  }

  const longestSide = Math.max(
    region.width,
    region.height
  );

  const targetLongestSide =
    region.name === 'full'
      ? 1800
      : 1400;

  if (longestSide < targetLongestSide) {
    const scale =
      targetLongestSide / longestSide;

    pipeline = pipeline.resize({
      width: Math.max(
        1,
        Math.round(
          region.width * scale
        )
      ),

      height: Math.max(
        1,
        Math.round(
          region.height * scale
        )
      ),

      fit: 'fill',

      kernel:
        mode === 'threshold'
          ? sharp.kernel.nearest
          : sharp.kernel.lanczos3
    });
  }

  return pipeline
    .flatten({
      background: '#ffffff'
    })
    .toColourspace('srgb')
    .ensureAlpha()
    .raw()
    .toBuffer({
      resolveWithObject: true
    });
}

function locationPoints(location) {
  if (!location) {
    return [];
  }

  return Object.values(location)
    .filter((point) => {
      return (
        point &&
        Number.isFinite(point.x) &&
        Number.isFinite(point.y)
      );
    });
}

function maskDetectedQr(
  rgbaData,
  width,
  height,
  location
) {
  const points = locationPoints(location);

  if (points.length === 0) {
    return;
  }

  const margin = 20;

  const minX = Math.max(
    0,
    Math.floor(
      Math.min(
        ...points.map(
          (point) => point.x
        )
      ) - margin
    )
  );

  const maxX = Math.min(
    width - 1,
    Math.ceil(
      Math.max(
        ...points.map(
          (point) => point.x
        )
      ) + margin
    )
  );

  const minY = Math.max(
    0,
    Math.floor(
      Math.min(
        ...points.map(
          (point) => point.y
        )
      ) - margin
    )
  );

  const maxY = Math.min(
    height - 1,
    Math.ceil(
      Math.max(
        ...points.map(
          (point) => point.y
        )
      ) + margin
    )
  );

  for (
    let y = minY;
    y <= maxY;
    y++
  ) {
    for (
      let x = minX;
      x <= maxX;
      x++
    ) {
      const index =
        (y * width + x) * 4;

      rgbaData[index] = 255;
      rgbaData[index + 1] = 255;
      rgbaData[index + 2] = 255;
      rgbaData[index + 3] = 255;
    }
  }
}

function decodeCodesFromPreparedImage(
  data,
  width,
  height
) {
  const sourceData =
    new Uint8ClampedArray(
      data.buffer,
      data.byteOffset,
      data.byteLength
    );

  const rgbaData =
    new Uint8ClampedArray(
      sourceData.length
    );

  rgbaData.set(sourceData);

  const results = [];

  for (
    let attempt = 0;
    attempt < MAX_CODES_PER_REGION;
    attempt++
  ) {
    const decoded = jsQR(
      rgbaData,
      width,
      height,
      {
        inversionAttempts: 'attemptBoth'
      }
    );

    if (!decoded?.data) {
      break;
    }

    const payload =
      String(decoded.data).trim();

    if (!payload) {
      break;
    }

    results.push(decoded);

    maskDetectedQr(
      rgbaData,
      width,
      height,
      decoded.location
    );
  }

  return results;
}

function mapPointToOriginal(
  point,
  region,
  processedWidth,
  processedHeight
) {
  return {
    x:
      region.left +
      point.x *
      (
        region.width /
        processedWidth
      ),

    y:
      region.top +
      point.y *
      (
        region.height /
        processedHeight
      )
  };
}

function mapLocationToOriginal(
  location,
  region,
  processedWidth,
  processedHeight
) {
  const mapped = {};

  for (
    const [
      name,
      point
    ] of Object.entries(
      location || {}
    )
  ) {
    if (
      !point ||
      !Number.isFinite(point.x) ||
      !Number.isFinite(point.y)
    ) {
      continue;
    }

    mapped[name] =
      mapPointToOriginal(
        point,
        region,
        processedWidth,
        processedHeight
      );
  }

  return mapped;
}

function calculateQrCenter(location) {
  const cornerNames = [
    'topLeftCorner',
    'topRightCorner',
    'bottomRightCorner',
    'bottomLeftCorner'
  ];

  const points = cornerNames
    .map((name) => location?.[name])
    .filter(Boolean);

  if (points.length === 0) {
    return {
      x: null,
      y: null
    };
  }

  return {
    x:
      points.reduce(
        (sum, point) =>
          sum + point.x,
        0
      ) / points.length,

    y:
      points.reduce(
        (sum, point) =>
          sum + point.y,
        0
      ) / points.length
  };
}

function isDuplicateCode(
  candidate,
  existingCodes
) {
  return existingCodes.some(
    (existing) => {
      if (
        existing.payload !==
        candidate.payload
      ) {
        return false;
      }

      if (
        candidate.center_x === null ||
        candidate.center_y === null ||
        existing.center_x === null ||
        existing.center_y === null
      ) {
        return true;
      }

      const distance = Math.hypot(
        candidate.center_x -
          existing.center_x,

        candidate.center_y -
          existing.center_y
      );

      return distance < 80;
    }
  );
}

async function scanRegions(
  sourceBuffer,
  regions,
  modes,
  finalCodes
) {
  for (const region of regions) {
    for (const mode of modes) {
      const {
        data,
        info
      } = await prepareRegion(
        sourceBuffer,
        region,
        mode
      );

      const decodedCodes =
        decodeCodesFromPreparedImage(
          data,
          info.width,
          info.height
        );

      for (const decoded of decodedCodes) {
        const mappedLocation =
          mapLocationToOriginal(
            decoded.location,
            region,
            info.width,
            info.height
          );

        const center =
          calculateQrCenter(
            mappedLocation
          );

        const candidate = {
          payload:
            String(
              decoded.data
            ).trim(),

          location:
            mappedLocation,

          center_x:
            center.x === null
              ? null
              : Number(
                  center.x.toFixed(2)
                ),

          center_y:
            center.y === null
              ? null
              : Number(
                  center.y.toFixed(2)
                ),

          preprocessing_mode:
            mode,

          region:
            region.name
        };

        if (
          !isDuplicateCode(
            candidate,
            finalCodes
          )
        ) {
          finalCodes.push(candidate);
        }
      }
    }
  }
}

async function decodeQr(buffer) {
  const source =
    await normalizeSourceImage(buffer);

  const regions =
    createSearchRegions(
      source.width,
      source.height
    );

  const codes = [];

  await scanRegions(
    source.buffer,
    regions,
    [
      'normal',
      'enhanced'
    ],
    codes
  );

  if (codes.length === 0) {
    await scanRegions(
      source.buffer,
      regions,
      [
        'threshold'
      ],
      codes
    );
  }

  codes.sort((first, second) => {
    const firstY =
      first.center_y ?? 0;

    const secondY =
      second.center_y ?? 0;

    if (firstY !== secondY) {
      return firstY - secondY;
    }

    return (
      (first.center_x ?? 0) -
      (second.center_x ?? 0)
    );
  });

  return {
    codes,
    image_width: source.width,
    image_height: source.height
  };
}

app.get('/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'qr-decoder',
    version: '2.0.0'
  });
});

app.post(
  '/decode',
  upload.single('file'),
  async (req, res) => {
    if (!req.file) {
      return res.status(200).json({
        qr_found: false,
        qr_count: 0,
        error:
          'Nu a fost primită imaginea în câmpul file'
      });
    }

    try {
      const result = await decodeQr(
        req.file.buffer
      );

      if (result.codes.length === 0) {
        return res.status(200).json({
          qr_found: false,
          qr_count: 0,

          filename:
            req.file.originalname,

          mime_type:
            req.file.mimetype,

          size_bytes:
            req.file.size,

          image_width:
            result.image_width,

          image_height:
            result.image_height,

          limitations: [
            'Nu a fost detectat un cod QR decodabil',
            (
              'Codul poate fi deteriorat, neclar, ' +
              'acoperit sau prea mic'
            )
          ]
        });
      }

      const codes = result.codes.map(
        (code, index) => {
          const payloadInfo =
            classifyPayload(
              code.payload
            );

          return {
            index: index + 1,

            payload:
              code.payload,

            ...payloadInfo,

            preprocessing_mode:
              code.preprocessing_mode,

            region:
              code.region,

            center_x:
              code.center_x,

            center_y:
              code.center_y,

            location:
              code.location
          };
        }
      );

      const firstCode = codes[0];

      return res.status(200).json({
        qr_found: true,
        qr_count: codes.length,

        filename:
          req.file.originalname,

        mime_type:
          req.file.mimetype,

        size_bytes:
          req.file.size,

        image_width:
          result.image_width,

        image_height:
          result.image_height,

        codes,

        /*
         * Compatibilitate cu workflow-ul actual:
         * aceste câmpuri reprezintă primul QR găsit.
         */
        payload:
          firstCode.payload,

        payload_type:
          firstCode.payload_type,

        scheme:
          firstCode.scheme ?? '',

        hostname:
          firstCode.hostname ?? '',

        port:
          firstCode.port ?? null,

        host:
          firstCode.host ?? '',

        should_execute: false,

        risk_level:
          firstCode.risk_level,

        preprocessing_mode:
          firstCode.preprocessing_mode,

        region:
          firstCode.region,

        center_x:
          firstCode.center_x,

        center_y:
          firstCode.center_y,

        location:
          firstCode.location,

        limitations: [
          (
            'Payload-urile au fost decodate, ' +
            'dar nu au fost executate'
          ),
          (
            'Imaginea a fost analizată integral ' +
            'și pe regiuni suprapuse'
          )
        ]
      });
    } catch (error) {
      return res.status(200).json({
        qr_found: false,
        qr_count: 0,

        filename:
          req.file.originalname,

        mime_type:
          req.file.mimetype,

        size_bytes:
          req.file.size,

        error:
          error instanceof Error
            ? error.message
            : String(error),

        limitations: [
          'Imaginea nu a putut fi procesată'
        ]
      });
    }
  }
);

app.use((error, _req, res, _next) => {
  res.status(200).json({
    qr_found: false,
    qr_count: 0,

    error:
      error instanceof Error
        ? error.message
        : String(error),

    limitations: [
      'Cererea nu a putut fi procesată'
    ]
  });
});

app.listen(
  PORT,
  '0.0.0.0',
  () => {
    console.log(
      `QR Decoder rulează pe portul ${PORT}`
    );
  }
);