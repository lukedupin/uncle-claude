import requests, json, sys, re
from rich.console import Console
from rich.markdown import Markdown


class JsonSettings:
    def __init__(self, filename, **kwargs):
        self.filename = filename
        for key in kwargs:
            setattr(self, key, kwargs[key])

    @staticmethod
    def load(filename):
        with open(filename, 'r') as f:
            return JsonSettings( filename, **json.load(f) )

    def save(self):
        with open(self.filename, 'w') as f:
            json.dump(self.__dict__, f)


target = JsonSettings.load(f'{sys.argv[1]}/target.json')
creds = JsonSettings.load(f'{sys.argv[1]}/creds.json')

headers = {
    'Content-Type': 'application/json',
    'User-Agent': target.user_agent,
}
cookies = {data.split('=')[0].strip(): data.split('=')[1].strip() for data in creds.cookies.split(';')}
data = {
    "prompt": sys.argv[2],
    "parent_message_uuid": creds.parent_uuid,
    "timezone": target.timezone,
    "attachments":[],
    "files":[],
    "rendering_mode":"raw"
}

# Swap out the user data in the url
url = re.sub(r'ORG', creds.org, target.url )
url = re.sub(r'CONV', creds.conversation, url )

# Post!
response = requests.post(
    url,
    headers=headers,
    cookies=cookies,
    data=json.dumps(data),
    stream=True
)

# Stream the reponse back to the terminal
buffer = ''
for line in response.iter_lines():
    if not line:
        continue

    # Process the line
    decoded_line = line.decode('utf-8')
    if not decoded_line.startswith('data: '):
        continue

    js = json.loads(decoded_line[6:])
    if js['type'] == 'completion':
        buffer += js['completion']
        sys.stdout.write('.')
        sys.stdout.flush()

print()
print()

# Dump in markdown
console = Console()
md = Markdown(buffer)
console.print(md)
