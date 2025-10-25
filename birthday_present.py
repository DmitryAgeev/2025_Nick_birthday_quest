# pip install qrcode
# pip install pillow

import base64
import hashlib
import zlib


def _k(n: int) -> bytes:
    h = hashlib
    _p = ''.join(map(chr, [
        0x50, 0x79, 0x74, 0x68, 0x6F, 0x6E,  # 'Python'
        0x33, 0x2E, 0x31, 0x30,  # '3.10'
        0x2D, 0x53, 0x65, 0x63, 0x72, 0x65, 0x74  # '-Secret'
    ]))
    _s = h.blake2b(
        "Соль? Да какая тут соль".encode("utf-8") + b"\xf0\x9f\x8d\x9a",
        digest_size=16, person=b"qr-obf"
    ).digest()
    return h.pbkdf2_hmac("sha256", _p.encode("utf-8"), _s, 200_000, dklen=n)


def _reveal_url() -> str:
    _blob_b64 = (
        "zzUcsRVEZHCBI+JJsXUQIkc3D7PvKAqLBHQna79noj6Cj9iyRtbmwpzbqTMVNHv"
        "ZXMlSDVNU/H6I/ytT867vtVREaaLu+z+ClAuRl4D2J9uNuXfjPSZ2ThEfXZfx6I"
        "JWy/F4aEqAFYiWGnks+/EIPTU="
    )
    _ct = base64.b64decode(_blob_b64)
    _ks = _k(len(_ct))
    _b85 = bytes(c ^ k for c, k in zip(_ct, _ks))
    _packed = base64.b85decode(_b85)
    return zlib.decompress(_packed).decode("utf-8")


def make_qr_png(outfile: str = "gift_qr.png") -> None:
    import qrcode
    url = _reveal_url()
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image()
    img.save(outfile)
    print(f"QR сохранён в {outfile}")


if __name__ == "__main__":
    make_qr_png()
