"""Pictures going to the model: paths found in typed or dropped text, files, the clipboard."""
import base64
import io
import os
import re
import urllib.parse
import urllib.request

from fusion_agent import term

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
ACCEPTED_FORMATS = ("PNG", "JPEG", "MPO", "WEBP")
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_SIDE = 1024

# A token is a double-quoted string, a single-quoted string, or a bare run of characters. On macOS and
# Linux a bare token may contain backslash escapes ("/Users/a\ b/x.png", as Terminal drops files);
# on Windows the backslash is the path separator ("C:\a b\x.png" comes quoted).
_POSIX_TOKEN = re.compile(r'"([^"\n]+)"|\'([^\'\n]+)\'|((?:\\.|[^\s"\'\\])+)')
_WINDOWS_TOKEN = re.compile(r'"([^"\n]+)"|\'([^\'\n]+)\'|([^\s"\']+)')


class ImageError(Exception):
    """A picture that cannot be sent (missing, too big, not an image)."""


class Attachment:
    """One picture for the model: a PNG, at most MAX_SIDE pixels on the long side."""

    def __init__(self, name, png_bytes, width, height, source_path=None):
        self.name = name
        self.png_bytes = png_bytes
        self.width = width
        self.height = height
        self.source_path = source_path

    @property
    def base64(self):
        return base64.b64encode(self.png_bytes).decode("ascii")


def _token_to_path(token, is_windows):
    if token.lower().startswith("file://"):
        parsed = urllib.parse.urlparse(token)
        path = urllib.request.url2pathname(parsed.path) if is_windows else urllib.parse.unquote(parsed.path)
        return path
    return os.path.expanduser(token)


def find_image_paths(text, is_windows=None, is_file=os.path.isfile):
    """Spans of existing picture files named in the text: a list of (start, end, path).
    The span covers the quotes too, so the whole dropped path can be replaced by a label."""
    if is_windows is None:
        is_windows = term.IS_WINDOWS
    pattern = _WINDOWS_TOKEN if is_windows else _POSIX_TOKEN
    found = []
    for match in pattern.finditer(text):
        if match.group(1) is not None:
            token = match.group(1)
        elif match.group(2) is not None:
            token = match.group(2)
        else:
            token = match.group(3)
            if not is_windows:
                token = re.sub(r"\\(.)", r"\1", token)
        path = _token_to_path(token.strip(), is_windows)
        if not path.lower().endswith(IMAGE_EXTENSIONS):
            continue
        if not is_file(path):
            continue
        found.append((match.start(), match.end(), path))
    return found


def attachment_from_image(image, name, source_path=None):
    """Downscale a Pillow image to MAX_SIDE and encode it as PNG (transparency on white)."""
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    if max(image.size) > MAX_SIDE:
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return Attachment(name, buffer.getvalue(), image.width, image.height, source_path)


def load_image(path):
    """Read a PNG/JPEG/WebP file up to 10 MB into an Attachment."""
    from PIL import Image, UnidentifiedImageError

    name = os.path.basename(path)
    try:
        size = os.path.getsize(path)
    except OSError:
        raise ImageError("%s: file not found" % path) from None
    if size > MAX_FILE_BYTES:
        raise ImageError("%s is %.1f MB; pictures up to 10 MB are taken" % (name, size / 1024 / 1024))
    try:
        with Image.open(path) as image:
            if image.format not in ACCEPTED_FORMATS:
                raise ImageError("%s is %s; PNG, JPEG and WebP are taken" % (name, image.format))
            image.load()
            return attachment_from_image(image, name, source_path=path)
    except (UnidentifiedImageError, OSError) as error:
        raise ImageError("%s is not a picture Pillow can read (%s)" % (name, error)) from None


def grab_clipboard():
    """Pictures in the clipboard: a copied image, or copied picture files. Raises ImageError."""
    try:
        from PIL import Image, ImageGrab
        content = ImageGrab.grabclipboard()
    except (ImportError, NotImplementedError, OSError) as error:
        raise ImageError("cannot read the clipboard here: %s" % error) from None
    if content is None:
        raise ImageError("no picture in the clipboard")
    if isinstance(content, Image.Image):
        return [attachment_from_image(content, "clipboard.png")]
    attachments = []
    if isinstance(content, list):
        for item in content:
            path = str(item)
            if path.lower().endswith(IMAGE_EXTENSIONS) and os.path.isfile(path):
                attachments.append(load_image(path))
    if not attachments:
        raise ImageError("the clipboard holds files, but no PNG, JPEG or WebP picture")
    return attachments
