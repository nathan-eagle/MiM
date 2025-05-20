from flask import Flask, request, render_template_string, redirect, url_for
import requests
import time
import webbrowser

app = Flask(__name__)

API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIzN2Q0YmQzMDM1ZmUxMWU5YTgwM2FiN2VlYjNjY2M5NyIsImp0aSI6IjVjMDQzZWU4MTc0Y2VlNmJiOTcxZjJjZTgwZTllZjMyNzU4ZTk5MDFhNGVmZDBmZGI1OGYwODI5OWZiODA5OTcwMjU4NDJlMzY3M2RmNWJjIiwiaWF0IjoxNzQ3MjU1MzUwLjYwOTY0LCJuYmYiOjE3NDcyNTUzNTAuNjA5NjQyLCJleHAiOjE3Nzg3OTEzNTAuNTk5OTA3LCJzdWIiOiIxMzU5NDIyOCIsInNjb3BlcyI6WyJzaG9wcy5tYW5hZ2UiLCJzaG9wcy5yZWFkIiwiY2F0YWxvZy5yZWFkIiwib3JkZXJzLnJlYWQiLCJvcmRlcnMud3JpdGUiLCJwcm9kdWN0cy5yZWFkIiwicHJvZHVjdHMud3JpdGUiLCJ3ZWJob29rcy5yZWFkIiwid2ViaG9va3Mud3JpdGUiLCJ1cGxvYWRzLnJlYWQiLCJ1cGxvYWRzLndyaXRlIiwicHJpbnRfcHJvdmlkZXJzLnJlYWQiLCJ1c2VyLmluZm8iXX0.OdAbVZp07b_jz_fI2rFoZObnb3iXQX7ktn69XlDT_TP8BuJZrFDbr1OtlhvmS9cq3XvQglWtk-iRRAuVNhQqCEPpQHgz781jPcC02C_iLBwgg3bviCwQn-C2HPqTgH4cLl7llajjG6Qle1yJVPOGZ55_QSdgm2QDVNcc7Aeb9n7AKo30w85a6OnksTbf_E0SKRi_GgRvtI1vGBvwXQFLXSvNzpJ-SEfgJtGkc-4_yGEHqopsljyZIywmnBv4nCR8i0EI_aSLKvSPPfX_FU-6UIUuNfqsLedSAF-hy2qNcU3M708rgla6BJTnTfJ-aCbiPDXW4ikxcegtNpbLD18_dBqYl34etzJr4LchGQaAp_vCtuV1AIWMxNE3LIssVa5BSpdyqoEPVCDeDVMqPWRUXJnAwfvCzcLLwWaplPKt1b1omiJynp8PRqvml7XgW_XgBIl5INNAjgyyfttZk79QVNHW5fhDLw-rh2zfazC83w4bTQCvA7JBE3VHgX-fIGuauezyhdw6Ve0KRm07y3jc0tq1C7ntG0fA6Mc0nBd6lseDQsLabCQxzdDngenABF1DNQFhwETXk11fByO6GTH7f408zWDAswjU5rsCFjubBzKJHnoTZMqgN88fPkEFPSnjtNFHy7hDrZlaMjlhRoDXXLPZv1b5SFzTarC3MBuHbCs"

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
    payload = {"url": image_url, "file_name": "logo.svg"}
    res = requests.post(upload_url, headers=headers, json=payload)
    res.raise_for_status()
    return res.json()["id"]

def create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids):
    product_payload = {
        "title": "Custom Product",
        "description": "A custom product with a logo.",
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
    res = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", headers=headers, json=product_payload)
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

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_term = request.form['search_term']
        image_url = request.form['image_url']
        
        blueprint_id, blueprint_title = find_blueprint_id(search_term)
        if not blueprint_id:
            return "No matching blueprint found."
        
        providers = get_print_providers(blueprint_id)
        if not providers:
            return f"No print providers found for blueprint {blueprint_id}."
        
        print_provider_id = providers[0]['id']
        
        shop_id = get_shop_id()
        image_id = upload_image(image_url)
        
        variants_url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
        r = requests.get(variants_url, headers=headers)
        r.raise_for_status()
        response_data = r.json()
        variant_ids = [v["id"] for v in response_data["variants"]]
        
        product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
        mockup_url = get_mockup_image(shop_id, product_id)
        
        return redirect(url_for('mockup', mockup_url=mockup_url))
    
    return render_template_string('''
        <form method="post">
            Search Term: <input type="text" name="search_term"><br>
            Image URL: <input type="text" name="image_url"><br>
            <input type="submit" value="Create Product">
        </form>
    ''')

@app.route('/mockup')
def mockup():
    mockup_url = request.args.get('mockup_url')
    return f'<img src="{mockup_url}" alt="Mockup">'

if __name__ == '__main__':
    app.run(debug=True)