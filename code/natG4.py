import requests, json, re, warnings

user_agent = "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"


class Model:
    def __init__(self, data):
        self.provider = data.get("provider")
        self.name = data.get("name")
        self.version = data.get("version")
        self.params = data.get("parameters")
        self.tag = f"{self.provider.strip()}:{self.name.strip()}"

    def resolve_params(self, kwargs):
        final_params = {}
        for param_name in self.params:
            if param_name in kwargs:
                final_params[param_name] = kwargs[param_name]
            else:
                final_params[param_name] = self.params[param_name]["value"]

        return final_params


class Client:
    api_url = "https://nat.dev/api"

    def __init__(self, token):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": user_agent,
            "Referrer": "https://nat.dev/",
            "Host": "nat.dev",
            "Authorization": f"Bearer {token}"
        }
        self.session.headers.update(self.headers)

        self.models = self.get_models()

    def get_models(self):
        models_url = self.api_url + "/all_models"
        r = self.session.get(models_url)
        data = r.json()

        models = {}
        for key in data:
            model = Model(data[key])
            models[key] = model

        return models

    def generate(self, model, prompt, **kwargs):
        if not isinstance(model, Model):
            model = self.models[model]

        generation_url = self.api_url + "/stream"
        payload = {
            "models": [
                {
                    "name": model.tag,
                    "parameters": model.resolve_params(kwargs),
                    "provider": model.provider,
                    "tag": model.tag,
                }
            ],
            "prompt": prompt
        }
        r = self.session.post(generation_url, json=payload, stream=True)

        for chunk in r.iter_content(chunk_size=None):
            r.raise_for_status()

            chunk_str = chunk.decode()
            data_regex = r"event:(\S+)\sdata:(.+)\s"
            matches = re.findall(data_regex, chunk_str)[0]

            data = json.loads(matches[1])
            data["event"] = matches[0]
            yield data


class Auth:
    api_url = "https://clerk.nat.dev/v1/client/sign_ins/"

    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "Host": "clerk.nat.dev",
            "User-Agent": user_agent,
            "Origin": "https://accounts.nat.dev"
        }
        self.session.params = {
            "_clerk_js_version": "4.32.6"
        }

        self.session.headers.update(self.headers)

    def check_errors(self, r):
        data = r.json()
        if r.status_code != 200:
            error_code = data["errors"][0]["code"]
            error_message = data["errors"][0]["long_message"]
            raise RuntimeError(f"{error_code}: {error_message}")

    # send verification email
    def send_otp_code(self, email_address):
        payload = {
            "identifier": email_address,
        }

        r = self.session.post(self.api_url, data=payload)
        data = r.json()
        self.check_errors(r)

        self.api_url_sia = data["response"]["id"]
        email_id = data["client"]["sign_in_attempt"]["supported_first_factors"][0]["email_address_id"]

        payload = {
            "email_address_id": email_id,
            "strategy": "email_code"
        }
        self.session.post(self.api_url + self.api_url_sia + "/prepare_first_factor", data=payload)

    # otp process
    def verify_otp_code(self, otp_code):
        payload = {
            "strategy": "email_code",
            "code": otp_code.strip()
        }
        r = self.session.post(self.api_url + self.api_url_sia + "/attempt_first_factor", data=payload)
        data = r.json()
        self.check_errors(r)

        if r.status_code != 200:
            print(r.text)

        token = data["client"]["sessions"][0]["last_active_token"]["jwt"]
        return token

    # old function names, deprecated
    def login_part_1(self, email_address):
        warnings.warn("Auth.login_part_1 is deprecated, use Auth.send_otp_code instead.")
        return self.send_otp_code(email_address)

    def login_part_2(self, code):
        warnings.warn("Auth.login_part_2 is deprecated, use Auth.verify_otp_code instead.")
        return self.verify_otp_code(code)


if __name__ == '__main__':
    # import openplayground

    email = "239144498@qq.com"
    token = ""
    # if email:
    #     auth = Auth()
    #     auth.send_otp_code(email)
    #     otp_code = input("enter otp key: ")
    #     token = auth.verify_otp_code(otp_code)
    #     print("Your token: " + token)
    #     print(token)

    client = Client(token)
    prompt = ""

    # openai:gpt-4
    # for chunk in client.generate("openai:gpt-3.5-turbo", prompt, maximum_length=1000):
    for chunk in client.generate("openai:gpt-4", prompt, maximum_length=32384):
        if chunk["event"] == "infer":
            print(chunk["message"], end="", flush=True)