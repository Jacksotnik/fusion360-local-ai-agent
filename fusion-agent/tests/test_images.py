"""Unit tests of pictures in (paths, files, labels) and out (inline display encodings)."""
import base64
import io
import os
import re
import tempfile
import unittest

from PIL import Image

from fusion_agent import display, images
from fusion_agent.repl import InputLabels


def existing(*paths):
    wanted = set(paths)
    return lambda path: path in wanted


class FindImagePathsTest(unittest.TestCase):
    def paths(self, text, is_windows, *files):
        return [path for _, _, path in images.find_image_paths(text, is_windows=is_windows, is_file=existing(*files))]

    def test_windows_quoted_path_with_spaces(self):
        text = 'посмотри "C:\\a b\\x.png" и сделай такую'
        self.assertEqual(self.paths(text, True, "C:\\a b\\x.png"), ["C:\\a b\\x.png"])
        start, end, _ = images.find_image_paths(text, is_windows=True, is_file=existing("C:\\a b\\x.png"))[0]
        self.assertEqual(text[start:end], '"C:\\a b\\x.png"')

    def test_windows_plain_path(self):
        self.assertEqual(self.paths("C:\\parts\\bracket.JPG сделай", True, "C:\\parts\\bracket.JPG"),
                         ["C:\\parts\\bracket.JPG"])

    def test_macos_escaped_spaces(self):
        text = "/Users/a\\ b/my\\ part.png сделай такую "
        self.assertEqual(self.paths(text, False, "/Users/a b/my part.png"), ["/Users/a b/my part.png"])

    def test_macos_single_quoted(self):
        self.assertEqual(self.paths("'/Users/a b/x.webp' ", False, "/Users/a b/x.webp"), ["/Users/a b/x.webp"])

    def test_file_url(self):
        self.assertEqual(self.paths("file:///Users/a%20b/x.png", False, "/Users/a b/x.png"), ["/Users/a b/x.png"])

    def test_tilde(self):
        expected = os.path.expanduser("~/x.png")
        self.assertEqual(self.paths("~/x.png", False, expected), [expected])

    def test_missing_file_and_other_extensions_are_ignored(self):
        self.assertEqual(self.paths("C:\\nope.png", True), [])
        self.assertEqual(self.paths("C:\\doc.pdf", True, "C:\\doc.pdf"), [])
        self.assertEqual(self.paths('"сделай пластину"', True), [])

    def test_several_paths(self):
        text = '"C:\\a b\\1.png" C:\\2.jpeg'
        self.assertEqual(self.paths(text, True, "C:\\a b\\1.png", "C:\\2.jpeg"), ["C:\\a b\\1.png", "C:\\2.jpeg"])


class LoadImageTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()

    def save(self, name, image, **options):
        path = os.path.join(self.folder, name)
        image.save(path, **options)
        return path

    def test_downscales_to_1024_and_returns_png(self):
        path = self.save("big.jpg", Image.new("RGB", (3000, 1500), (200, 10, 10)), quality=90)
        attachment = images.load_image(path)
        self.assertEqual((attachment.width, attachment.height), (1024, 512))
        self.assertTrue(attachment.png_bytes.startswith(b"\x89PNG"))
        self.assertEqual(attachment.name, "big.jpg")
        self.assertEqual(base64.b64decode(attachment.base64), attachment.png_bytes)

    def test_small_image_keeps_its_size_and_transparency_goes_white(self):
        path = self.save("small.png", Image.new("RGBA", (40, 30), (0, 0, 0, 0)))
        attachment = images.load_image(path)
        self.assertEqual((attachment.width, attachment.height), (40, 30))
        with Image.open(io.BytesIO(attachment.png_bytes)) as image:
            self.assertEqual(image.convert("RGB").getpixel((5, 5)), (255, 255, 255))

    def test_webp(self):
        path = self.save("part.webp", Image.new("RGB", (64, 64), (0, 100, 0)))
        self.assertEqual(images.load_image(path).width, 64)

    def test_avif(self):
        path = self.save("part.avif", Image.new("RGB", (64, 64), (0, 100, 0)))
        self.assertEqual(images.load_image(path).width, 64)

    def test_rejects_big_files_and_non_images(self):
        path = os.path.join(self.folder, "huge.png")
        with open(path, "wb") as file:
            file.write(b"\0" * (images.MAX_FILE_BYTES + 1))
        with self.assertRaises(images.ImageError):
            images.load_image(path)
        text_path = os.path.join(self.folder, "fake.png")
        with open(text_path, "w") as file:
            file.write("not a picture")
        with self.assertRaises(images.ImageError):
            images.load_image(text_path)
        gif_path = self.save("anim.png.gif", Image.new("RGB", (8, 8)))
        os.replace(gif_path, os.path.join(self.folder, "gif.png"))
        with self.assertRaises(images.ImageError):
            images.load_image(os.path.join(self.folder, "gif.png"))


class InputLabelsTest(unittest.TestCase):
    def attachment(self, name, path=None):
        return images.Attachment(name, b"\x89PNG", 1, 1, source_path=path)

    def test_expand_removes_picture_labels_and_restores_pastes(self):
        labels = InputLabels()
        picture = labels.add_image(self.attachment("part.png"))
        paste = labels.add_paste("a\nb\nc\nd")
        self.assertEqual(picture, "[Image: part.png]")
        self.assertEqual(paste, "[Pasted text #1, 4 lines]")
        request, attachments = labels.expand("%s сделай такую ↵ и ещё %s" % (picture, paste))
        self.assertEqual(request, "сделай такую \n и ещё a\nb\nc\nd")
        self.assertEqual([attachment.name for attachment in attachments], ["part.png"])

    def test_same_name_gets_a_number(self):
        labels = InputLabels()
        self.assertEqual(labels.add_image(self.attachment("x.png")), "[Image: x.png]")
        self.assertEqual(labels.add_image(self.attachment("x.png")), "[Image: x.png #2]")

    def test_unknown_label_stays_as_text(self):
        request, attachments = InputLabels().expand("[Image: gone.png] сделай")
        self.assertEqual(request, "[Image: gone.png] сделай")
        self.assertEqual(attachments, [])

    def test_history_keeps_paths(self):
        labels = InputLabels()
        label = labels.add_image(self.attachment("x.png", path="C:\\a b\\x.png"))
        self.assertEqual(labels.for_history(label + " сделай"), '"C:\\a b\\x.png" сделай')


def decode_sixel(data):
    """A small Sixel decoder: {(x, y): register} of every painted pixel."""
    body = data[data.index("q") + 1:data.rindex("\x1b\\")]
    painted = {}
    x = 0
    band = 0
    color = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == '"':
            match = re.match(r'"[\d;]*', body[index:])
            index += len(match.group(0))
            continue
        if char == "#":
            match = re.match(r"#(\d+)(;2;\d+;\d+;\d+)?", body[index:])
            color = int(match.group(1))
            index += len(match.group(0))
            continue
        if char == "$":
            x = 0
            index += 1
            continue
        if char == "-":
            x = 0
            band += 1
            index += 1
            continue
        count = 1
        if char == "!":
            match = re.match(r"!(\d+)(.)", body[index:])
            count = int(match.group(1))
            char = match.group(2)
            index += len(match.group(0))
        else:
            index += 1
        value = ord(char) - 63
        for _ in range(count):
            for row in range(6):
                if value & (1 << row):
                    painted[(x, band * 6 + row)] = color
            x += 1
    return painted


class DisplayTest(unittest.TestCase):
    def test_sixel_round_trip(self):
        image = Image.new("RGB", (37, 20), (255, 255, 255))
        for x in range(10, 30):
            for y in range(3, 15):
                image.putpixel((x, y), (200, 30, 30))
        image.putpixel((36, 19), (0, 0, 255))
        paletted = image.quantize(colors=8, dither=Image.Dither.NONE)
        painted = decode_sixel(display.sixel_sequence(paletted))
        for y in range(20):
            for x in range(37):
                self.assertEqual(painted.get((x, y)), paletted.getpixel((x, y)), (x, y))

    def test_sixel_from_png_is_scaled(self):
        buffer = io.BytesIO()
        Image.new("RGB", (1000, 800), (90, 90, 90)).save(buffer, format="PNG")
        data = display.sixel_sequence_from_png(buffer.getvalue())
        self.assertIn('"1;1;%d;416' % display.SIXEL_WIDTH_PX, data)

    def test_kitty_chunks(self):
        data = display.kitty_sequence(b"x" * 10000, 40)
        chunks = re.findall(r"\x1b_G([^;]*);([^\x1b]*)\x1b\\", data)
        self.assertTrue(chunks[0][0].startswith("a=T,f=100,c=40,m=1"))
        self.assertEqual(chunks[-1][0], "m=0")
        self.assertEqual(base64.b64decode("".join(chunk for _, chunk in chunks)), b"x" * 10000)

    def test_iterm(self):
        data = display.iterm_sequence(b"abc", 50)
        self.assertTrue(data.startswith("\x1b]1337;File=inline=1;size=3;width=50;"))
        self.assertTrue(data.endswith(base64.b64encode(b"abc").decode() + "\x07"))

    def test_detect_protocol(self):
        self.assertEqual(display.detect_protocol({"TERM_PROGRAM": "iTerm.app"}), "iterm")
        self.assertEqual(display.detect_protocol({"TERM_PROGRAM": "WezTerm"}), "iterm")
        self.assertEqual(display.detect_protocol({"KITTY_WINDOW_ID": "1"}), "kitty")
        self.assertEqual(display.detect_protocol({"WT_SESSION": "x"}), "sixel")
        self.assertIsNone(display.detect_protocol({"TERM_PROGRAM": "Apple_Terminal"}))
        self.assertIsNone(display.detect_protocol({"WT_SESSION": "x", "TMUX": "1"}))
        self.assertIsNone(display.detect_protocol({"WT_SESSION": "x", "FUSION_AGENT_INLINE_IMAGES": "off"}))
        self.assertEqual(display.detect_protocol({"FUSION_AGENT_INLINE_IMAGES": "kitty"}), "kitty")


if __name__ == "__main__":
    unittest.main()
