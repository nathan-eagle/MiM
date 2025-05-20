import requests
import time
import webbrowser

# Fron API docs: https://developers.printify.com/#overview
# x: "Horizontal position of the image. Value is a float between 0 and 1, where 0 is the left edge and 1 is the right edge."
# y: "Vertical position of the image. Value is a float between 0 and 1, where 0 is the top edge and 1 is the bottom edge."
#Therefore:
# x = 0.5 means the image is horizontally centered.
# y = 0.5 means the image is vertically centered.

API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzN2Q0YmQzMDM1ZmUxMWU5YTgwM2FiN2VlYjNjY2M5NyIsImp0aSI6IjVjMDQzZWU4MTc0Y2VlNmJiOTcxZjJjZTgwZTllZjMyNzU4ZTk5MDFhNGVmZDBmZGI1OGYwODI5OWZiODA5OTcwMjU4NDJlMzY3M2RmNWJjIiwiaWF0IjoxNzQ3MjU1MzUwLjYwOTY0LCJuYmYiOjE3NDcyNTUzNTAuNjA5NjQyLCJleHAiOjE3Nzg3OTEzNTAuNTk5OTA3LCJzdWIiOiIxMzU5NDIyOCIsInNjb3BlcyI6WyJzaG9wcy5tYW5hZ2UiLCJzaG9wcy5yZWFkIiwiY2F0YWxvZy5yZWFkIiwib3JkZXJzLnJlYWQiLCJvcmRlcnMud3JpdGUiLCJwcm9kdWN0cy5yZWFkIiwicHJvZHVjdHMud3JpdGUiLCJ3ZWJob29rcy5yZWFkIiwid2ViaG9va3Mud3JpdGUiLCJ1cGxvYWRzLnJlYWQiLCJ1cGxvYWRzLndyaXRlIiwicHJpbnRfcHJvdmlkZXJzLnJlYWQiLCJ1c2VyLmluZm8iXX0.OdAbVZp07b_jz_fI2rFoZObnb3iXQX7ktn69XlDT_TP8BuJZrFDbr1OtlhvmS9cq3XvQglWtk-iRRAuVNhQqCEPpQHgz781jPcC02C_iLBwgg3bviCwQn-C2HPqTgH4cLl7llajjG6Qle1yJVPOGZ55_QSdgm2QDVNcc7Aeb9n7AKo30w85a6OnksTbf_E0SKRi_GgRvtI1vGBvwXQFLXSvNzpJ-SEfgJtGkc-4_yGEHqopsljyZIywmnBv4nCR8i0EI_aSLKvSPPfX_FU-6UIUuNfqsLedSAF-hy2qNcU3M708rgla6BJTnTfJ-aCbiPDXW4ikxcegtNpbLD18_dBqYl34etzJr4LchGQaAp_vCtuV1AIWMxNE3LIssVa5BSpdyqoEPVCDeDVMqPWRUXJnAwfvCzcLLwWaplPKt1b1omiJynp8PRqvml7XgW_XgBIl5INNAjgyyfttZk79QVNHW5fhDLw-rh2zfazC83w4bTQCvA7JBE3VHgX-fIGuauezyhdw6Ve0KRm07y3jc0tq1C7ntG0fA6Mc0nBd6lseDQsLabCQxzdDngenABF1DNQFhwETXk11fByO6GTH7f408zWDAswjU5rsCFjubBzKJHnoTZMqgN88fPkEFPSnjtNFHy7hDrZlaMjlhRoDXXLPZv1b5SFzTarC3MBuHbCs"
IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/a/a7/React-icon.svg"
PRODUCT_TITLE = "Custom React Logo Tote Bag"
PRODUCT_DESCRIPTION = "A tote bag featuring the React logo."
SEARCH_TERM = "tote" #can replace with hundreds of products like 'tank', 'shirt', 'underwear'(!)

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "PythonScript"
}

def find_blueprint_id(search_term):
    url = "https://api.printify.com/v1/catalog/blueprints.json"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    blueprints = res.json()
    for blueprint in blueprints:
        if search_term.lower() in blueprint['title'].lower():
            return blueprint['id'], blueprint['title']
    return None, None

def get_print_providers(blueprint_id):
    url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers.json"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    providers = res.json()
    return providers

def get_shop_id():
    res = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
    res.raise_for_status()
    return res.json()[0]["id"]

def upload_image(image_url):
    upload_url = "https://api.printify.com/v1/uploads/images.json"
    payload = {"url": image_url, "file_name": "react-logo.svg"}
    res = requests.post(upload_url, headers=headers, json=payload)
    print("Upload response status:", res.status_code)
    print("Upload response body:", res.text)
    res.raise_for_status()
    return res.json()["id"]

def create_product(shop_id):
    # Find blueprint and provider for 'tote'
    blueprint_id, blueprint_title = find_blueprint_id(SEARCH_TERM)
    if not blueprint_id:
        raise Exception("No matching blueprint found for ", SEARCH_TERM)
    providers = get_print_providers(blueprint_id)
    if not providers:
        raise Exception(f"No print providers found for blueprint {blueprint_id}.")
    print_provider_id = providers[0]['id']
    print(f"Using blueprint: {blueprint_title} (ID: {blueprint_id}) and provider ID: {print_provider_id}")

    # Fetch product variants
    variants_url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
    r = requests.get(variants_url, headers=headers)
    r.raise_for_status()
    response_data = r.json()
    variant_ids = [v["id"] for v in response_data["variants"]]

    # Upload image and get image id
    image_id = upload_image(IMAGE_URL)

    product_payload = {
        "title": PRODUCT_TITLE,
        "description": PRODUCT_DESCRIPTION,
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": [{"id": vid, "price": 1999, "is_enabled": True} for vid in variant_ids],
        "print_areas": [
            {
                "variant_ids": variant_ids,
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": image_id,
                                "angle": 0,
                                "x": .5,
                                "y": .5,
                                "scale": 1
                            }
                        ]
                    }
                ]
            }
        ]
    }

    print("Request payload:", product_payload)  # Debug print
    res = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", headers=headers, json=product_payload)
    print("Response status:", res.status_code)  # Debug print
    print("Response body:", res.text)  # Debug print
    res.raise_for_status()
    return res.json()["id"]

def get_mockup_image(shop_id, product_id):
    for _ in range(10):  # wait for mockup generation
        res = requests.get(f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json", headers=headers)
        res.raise_for_status()
        product = res.json()
        images = product.get("images", [])
        if images:
            return images[0]["src"]
        time.sleep(3)
    raise Exception("Mockup not generated in time.")

def main():
    print("Fetching shop ID...")
    shop_id = get_shop_id()

    print("Creating product...")
    product_id = create_product(shop_id)

    print("Waiting for mockup...")
    mockup_url = get_mockup_image(shop_id, product_id)

    print(f"Opening mockup image: {mockup_url}")
    webbrowser.open(mockup_url)

if __name__ == "__main__":
    main()
