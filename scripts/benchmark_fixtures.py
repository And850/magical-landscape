from PIL import Image, ImageDraw


def layout(second=False):
    labels = Image.new("L", (512, 512), 0)
    d = ImageDraw.Draw(labels)
    if not second:
        d.rectangle((0, 280, 511, 511), fill=1)
        d.polygon([(0, 280), (110, 110), (230, 280)], fill=2)
        d.polygon([(270, 280), (385, 150), (511, 280)], fill=2)
        d.rectangle((170, 350, 360, 511), fill=3)
        d.rectangle((35, 285, 130, 415), fill=4)
        d.rectangle((355, 280, 440, 380), fill=6)
    else:
        d.rectangle((0, 170, 511, 511), fill=3)
        d.ellipse((40, 240, 240, 420), fill=1)
        d.ellipse((330, 150, 510, 300), fill=1)
        d.rectangle((95, 265, 165, 355), fill=6)
        d.ellipse((350, 170, 440, 245), fill=4)
        d.ellipse((210, 385, 250, 410), fill=5)
    return labels
