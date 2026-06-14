
import cairosvg

def convert_svg_to_png(svg_file="porter_diagram.svg", png_file="porter_diagram.png"):
    # 300 DPI is roughly 4.16x the default 72 DPI
    cairosvg.svg2png(url=svg_file, write_to=png_file, scale=4.16)

if __name__ == "__main__":
    convert_svg_to_png()
