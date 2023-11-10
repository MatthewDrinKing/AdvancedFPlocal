import requests
from retrying import retry
import json
import time

# Load configuration settings from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Define a retry decorator
@retry(stop_max_attempt_number=3, wait_fixed=2000)  # Retry 3 times with a 2-second delay
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

    response = requests.post('https://testing-prod.requestcatcher.com/', data=printer_xml, headers=headers)
    if response.status_code == 200:
        print("Printing:", printer_xml)
        print("Response:", response.text)

        # Check if the response contains data before parsing it as JSON
        if response.text:
            try:
                response_data = response.json()
                add_info = response_data.get('soapenv:Envelope', {}).get('soapenv:Body', {}).get('response', {}).get('addInfo', {})
                fiscal_receipt_number = add_info.get('fiscalReceiptNumber', 'N/A')
                fiscal_receipt_amount = add_info.get('fiscalReceiptAmount', 'N/A')
                fiscal_receipt_date = add_info.get('fiscalReceiptDate', 'N/A')
                fiscal_receipt_time = add_info.get('fiscalReceiptTime', 'N/A')
                serial_number = add_info.get('serialNumber', 'N/A')

                print(f"Fiscal Receipt Number: {fiscal_receipt_number}")
                print(f"Fiscal Receipt Amount: {fiscal_receipt_amount}")
                print(f"Fiscal Receipt Date: {fiscal_receipt_date}")
                print(f"Fiscal Receipt Time: {fiscal_receipt_time}")
                print(f"Serial Number: {serial_number}")
            except json.JSONDecodeError:
                print("Error decoding JSON response")
    else:
        print("Printing failed")


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
                    try_execute_print(order)

                    # Update the order with the fiscal ID
                    # Check if 'id' is available in the order before accessing it
                    if 'id' in order:
                        order_id = order['id']
                        fiscal_id = "<fiscal_id_from_response>"
                        update_response = requests.post(f'{config["middle_server_address"]}/orders/{order_id}/update', data={"fiscal_id": fiscal_id})

                        if update_response.status_code == 200:
                            print(f"Order {order_id} updated with fiscal ID {fiscal_id}")

            except json.JSONDecodeError:
                print("Error decoding JSON response")
        else:
            print("Failed to fetch orders")

        time.sleep(config['poll_interval_seconds'])

if __name__ == "__main__":
    main()
