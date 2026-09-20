from PIL import Image
p = '/media/uti120s/Images/IMG 0418.bmp'
img = Image.open(p)
print('Format:', img.format, 'Size:', img.size, 'Mode:', img.mode)
img.save('/home/pi/plant-stress-ndvi/static/last_thermal.jpg')
print('SUCCESS: Converted to /home/pi/plant-stress-ndvi/static/last_thermal.jpg')
