import requests

def get_exchange_rate(base_currency: str = "USD"):
    try:
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency.upper()}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if "rates" in data:
            rates = data["rates"]
            # Just grab a few popular currencies for a quick summary, 
            # or the agent can ask for a specific target.
            popular = {k: rates[k] for k in ["INR", "EUR", "GBP", "JPY", "AED", "AUD", "CAD"] if k in rates}
            
            result = f"Exchange rates based on 1 {base_currency.upper()}:\n"
            for curr, rate in popular.items():
                result += f"- 1 {base_currency.upper()} = {rate} {curr}\n"
            return result
        return "Currency rates unavailable."
    except Exception as e:
        return f"Error fetching exchange rates: {e}"

if __name__ == "__main__":
    print(get_exchange_rate("USD"))
