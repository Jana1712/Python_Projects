from PIL import Image, ImageDraw, ImageFont
import os

names = [
"Arunachalam",
"Chandrabose",
"Parameshwar",
"Ramasundari",
"Subramanian",
"Krishnapras",
"Vishnupathi",
"Ranganathan",
"Thirumalini",
"Rajendiran",
]

os. makedirs('Certificates', exist_ok=True)

for index,name in enumerate(names, start=1):
    
    certificate_template = Image.open('certificate.png')
    
    draw = ImageDraw.Draw(certificate_template)
    
    font = ImageFont.truetype("DancingScript-Regular.ttf",120)
    
    text_position = (670,613)
    
    draw.text(text_position,name,fill="black",font=font)
    
    safe_filename = f"{name}.png"
    
    output_folder = os.path.join("Certificates",safe_filename)
    
    
    certificate_template.save(output_folder)
    
    print(f'{index}, Certificate Generator for the name {name}')
    
    