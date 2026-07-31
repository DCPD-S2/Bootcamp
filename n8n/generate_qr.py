import qrcode

url = "https://www.amtso.org/check-desktop-phishing-page/"

qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=12,
    border=4,
)

qr.add_data(url)
qr.make(fit=True)

image = qr.make_image(
    fill_color="black",
    back_color="white",
)

image.save("qr_test_phishing.png")

print("QR creat pentru:", url)