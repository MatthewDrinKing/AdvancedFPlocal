import requests
from retrying import retry
import json
import time
import xml.etree.ElementTree as ET

# Load configuration settings from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Define a retry decorator
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def try_execute_print(order):
    OPERATOR_ID = 1
    subtotal = 0
    total = 0
    items_xml = ""

    item_group = order  # Use the order directly, not a nested 'items' list

    item_subtotal = float(item_group['price']) * int(item_group['quantity'])
    subtotal += item_subtotal
    items_xml += f'<printRecItem description="{item_group["name"]}" quantity="{item_group["quantity"]}" unitPrice="{item_group["price"]}" department="1" operator="{OPERATOR_ID}" justification="1" />'

    total = f'{subtotal:.2f}'
    items_xml += f'<printRecTotal operator="{OPERATOR_ID}" description="CARTA DI CREDITO" payment="{total}" paymentType="2" index="1" justification="1" />'

    printer_xml = f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><printerFiscalReceipt><beginFiscalReceipt operator="{OPERATOR_ID}" />{items_xml}<endFiscalReceipt operator="{OPERATOR_ID}" /></printerFiscalReceipt></s:Body></s:Envelope>'

    headers = {
        'Content-Type': 'text/xml; charset=UTF-8',
        'SOAPAction': ''
    }

    response = requests.post(config["fiscal_printer_address"], data=printer_xml, headers=headers)
    if response.status_code == 200:
        print("Printing:", printer_xml)
        print("Response:", response.text)

        # Parse the XML response
        try:
            root = ET.fromstring(response.text)
            response_elem = root.find('.//response')
            if response_elem is not None and response_elem.attrib['success'] == 'true':
                add_info = response_elem.find('addInfo')
                fiscal_receipt_number = add_info.find('fiscalReceiptNumber').text

                # Print the fiscal receipt number
                print(f"Fiscal Receipt Number: {fiscal_receipt_number}")

                return fiscal_receipt_number
            else:
                print("Error in response or response unsuccessful")
                return None
        except ET.ParseError:
            print("Error parsing XML response")
            return None
    else:
        print("Printing failed")
        return None

def main():
    while True:
        # Poll the middle server for orders
        response = requests.get(f'{config["middle_server_address"]}/orders/{config["venue_name"]}')
        if response.status_code == 200:
            print("Response:", response.text)  # Print the response content for debugging

            try:
                orders = response.json()

                # Process orders and send to fiscal printer
                for order in orders:
                    fiscal_receipt_number = try_execute_print(order)

                    if fiscal_receipt_number:
                        # Update the order with the fiscal ID
                        if 'id' in order:
                            order_id = order['id']
                            update_response = requests.post(f'{config["middle_server_address"]}/orders/{order_id}/update', data={"fiscal_id": fiscal_receipt_number})

                            if update_response.status_code == 200:
                                print(f"Order {order_id} updated with fiscal ID {fiscal_receipt_number}")

            except json.JSONDecodeError:
                print("Error decoding JSON response")
        else:
            print("Failed to fetch orders")

        time.sleep(config['poll_interval_seconds'])

if __name__ == "__main__":
    main()