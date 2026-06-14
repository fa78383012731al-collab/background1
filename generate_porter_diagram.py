
import svgwrite

def create_porter_diagram(filename="porter_diagram.svg"):
    dwg = svgwrite.Drawing(filename, profile='tiny', size=('100%', '100%'))
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), fill='white', opacity=0))

    # Define colors (approximated from the image)
    dark_blue = '#2C5F8D'
    medium_blue = '#4A8BBF'
    light_blue = '#7CB9E8'
    green = '#5CB85C'
    teal = '#4CAF50'
    text_color = '#333333'
    header_text_color = 'white'

    # Main title
    dwg.add(dwg.text('الضغط التنافسي: قوى بورتر الخمسة', insert=(50, 50), fill=text_color, font_size='24px', font_family='Arial, sans-serif', text_anchor='start', direction='rtl'))

    # Center element: Hospital
    center_x, center_y = 400, 300
    dwg.add(dwg.circle(center=(center_x, center_y), r=70, fill=dark_blue))
    dwg.add(dwg.text('مستشفى', insert=(center_x, center_y - 10), fill='white', font_size='16px', font_family='Arial, sans-serif', text_anchor='middle', direction='rtl'))
    dwg.add(dwg.text('الشاعر الخاص', insert=(center_x, center_y + 15), fill='white', font_size='16px', font_family='Arial, sans-serif', text_anchor='middle', direction='rtl'))

    # Box dimensions and common styles
    box_width = 250
    box_height = 100
    header_height = 30
    padding = 10
    text_line_height = 18

    # Function to create a box with header and body text
    def create_info_box(x, y, header_text, body_text, header_color, box_color='white'):
        # Header rectangle
        dwg.add(dwg.rect(insert=(x, y), size=(box_width, header_height), fill=header_color, rx=5, ry=5))
        dwg.add(dwg.text(header_text, insert=(x + box_width / 2, y + header_height / 2 + 5), fill=header_text_color, font_size='14px', font_family='Arial, sans-serif', text_anchor='middle', direction='rtl'))

        # Body rectangle
        dwg.add(dwg.rect(insert=(x, y + header_height), size=(box_width, box_height - header_height), fill=box_color, rx=5, ry=5))
        
        # Body text (split into lines)
        lines = body_text.split('،') # Split by comma for better line breaks
        current_y = y + header_height + padding + 5
        for line in lines:
            dwg.add(dwg.text(line.strip(), insert=(x + box_width - padding, current_y), fill=text_color, font_size='12px', font_family='Arial, sans-serif', text_anchor='end', direction='rtl'))
            current_y += text_line_height

    # Define box positions
    # Top Left
    create_info_box(center_x - 350, center_y - 200, 'حدة المنافسة (3.5/5)', 'منافسة قوية بين 3 منشآت خاصة و6 حكومية حول السعر والموقع. (الرقمنة هي المهرب الوحيد).', dark_blue)
    # Top Right
    create_info_box(center_x + 100, center_y - 200, 'قوة المشترين (4/5)', 'وعي المريض يرتفع، وحساسيته للجودة تتفوق على السعر في حال توفر التجربة الممتازة.', medium_blue)
    # Middle Right
    create_info_box(center_x + 100, center_y, 'قوة الموردين (3/5)', 'قوة تفاوضية عالية للكوادر الطبية المتخصصة.', light_blue)
    # Bottom Right
    create_info_box(center_x + 100, center_y + 200, 'الداخلون الجدد (3/5)', 'حواجز دخول مالية عالية (30 مليون+)، لكن التهديد قادم من العيادات الرقمية.', green)
    # Bottom Left
    create_info_box(center_x - 350, center_y + 200, 'المنتجات البديلة (2.5/5)', 'الطب التقليدي، والسفر للعلاج (المريض يفضل الرعاية المحلية إذا توفرت الجودة).', teal)

    # Connectors (simplified for now, will refine if needed)
    # From center to top-left
    dwg.add(dwg.line(start=(center_x - 70 * 0.707, center_y - 70 * 0.707), end=(center_x - 350 + box_width/2, center_y - 200 + header_height/2), stroke=dark_blue, stroke_width=3))
    # From center to top-right
    dwg.add(dwg.line(start=(center_x + 70 * 0.707, center_y - 70 * 0.707), end=(center_x + 100 + box_width/2, center_y - 200 + header_height/2), stroke=medium_blue, stroke_width=3))
    # From center to middle-right
    dwg.add(dwg.line(start=(center_x + 70, center_y), end=(center_x + 100, center_y + header_height/2), stroke=light_blue, stroke_width=3))
    # From center to bottom-right
    dwg.add(dwg.line(start=(center_x + 70 * 0.707, center_y + 70 * 0.707), end=(center_x + 100 + box_width/2, center_y + 200 + header_height/2), stroke=green, stroke_width=3))
    # From center to bottom-left
    dwg.add(dwg.line(start=(center_x - 70 * 0.707, center_y + 70 * 0.707), end=(center_x - 350 + box_width/2, center_y + 200 + header_height/2), stroke=teal, stroke_width=3))

    dwg.save()

if __name__ == '__main__':
    create_porter_diagram()
