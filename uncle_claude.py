import requests, json, sys, re, pyperclip
from rich.console import Console
from rich.markdown import Markdown


# Handy class for loading json files
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

# Load up my content
target = JsonSettings.load(f'{sys.argv[1]}/target.json')
creds = JsonSettings.load(f'{sys.argv[1]}/creds.json')
prompts = JsonSettings.load(f'{sys.argv[1]}/prompts.json')

# Setup the prompt
prompt = sys.argv[2]
if prompt.startswith('-p'):
    if len(splt := prompt.split(' ')) > 1:
        preset = splt[0][2:]
        prompt = ' '.join(splt[1:])
        if preset in prompts.prompts:
            raw = prompts.prompts[preset]
            if 'PROMPT' in raw:
                prompt = re.sub(r'PROMPT', prompt, raw)
            else:
                prompt = f"{raw} {prompt}"
        else:
            print(f'Prompt preset "{preset}" not found')
            sys.exit(1)

# Setup the request
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

# Copy the first code block to the clipboard
for token in md.parsed:
    if token.type == 'fence':
        pyperclip.copy(token.content)
        break
