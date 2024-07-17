import argparse
import requests
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time

def download_image(url):
    response = requests.get(url)
    response.raise_for_status()  # Check if the request was successful
    return Image.open(BytesIO(response.content))

def concatenate_images_horizontally(image1, image2):
    # Get the dimensions of the images
    width1, height1 = image1.size
    width2, height2 = image2.size

    # Create a new image with the combined width and the max height of the two images
    new_image = Image.new('RGB', (width1 + width2, max(height1, height2)))

    # Paste the images into the new image
    new_image.paste(image1, (0, 0))
    new_image.paste(image2, (width1, 0))

    return new_image

def display_image(image):
    plt.figure(figsize=(25,8))
    plt.imshow(image)
    plt.axis('off')  # Turn off axis numbers and ticks
    plt.show()

def main(gene):
	# set up WebDriver
	driver = webdriver.Chrome()

	try:
		# Navigate to RiceXPro
		driver.get("https://ricexpro.dna.affrc.go.jp/RXP_4001/")

		# Find search box and button
		search_box = driver.find_element(By.NAME, "keyword")
		search_button = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Search']")

		# search gene
		search_box.send_keys(args.gene)
		search_button.click()

		# get the URLs for each graph
		try:
			element = driver.find_element(By.CLASS_NAME, "graph-link")
		except NoSuchElementException:
			print("No hits for",args.gene)
			return False

		# if there is a hit
		pre = "https://ricexpro.dna.affrc.go.jp/RXP_4001/"
		dev = pre + element.get_attribute("dev_barimg")
		tissue = pre + element.get_attribute("tissue_barimg")

		# get the barplots and combine them
		image1 = download_image(dev)
		image2 = download_image(tissue)

		# Concatenate the images horizontally
		im = concatenate_images_horizontally(image1, image2)
		display_image(im)		

	finally:
		driver.quit()


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Gene to search on RiceXPro.")
	parser.add_argument("gene", type=str)
	args = parser.parse_args()

	while True:
		if not main(args.gene):
			break
