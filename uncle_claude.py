import uuid

import requests, json, sys, re, os, time
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
        js = {k: getattr(self, k) for k in self.__dict__ if k not in ['filename']}
        with open(self.filename, 'w') as f:
            json.dump(js, f, indent=4)


# Swap out the user data in the url
def url( creds, target ):
    target = re.sub(r'ORG', creds.org, target)
    target = re.sub(r'CONV', creds.conversation, target)
    return target


# Load up my content
target = JsonSettings.load(f'{sys.argv[1]}/target.json')
creds = JsonSettings.load(f'{sys.argv[1]}/creds.json')
user_prompts = JsonSettings.load(f'{sys.argv[1]}/prompts.json')

# Load up the parent_uuid
parent_uuid = '00000000-0000-4000-8000-000000000000'
try:
    with open(f'{sys.argv[1]}/parent_uuid', 'r') as f:
        if len(pu := f.read().strip()) == 36:
            parent_uuid = pu
except FileNotFoundError:
    pass

create_conv = False

# Setup the prompt
prompt_args = sys.argv[2].split(' ')
while len(prompt_args) > 0:
    prompt = prompt_args[0]

    # Match args while we get them
    if prompt.startswith('-p'):
        if len(splt := prompt.split(' ')) > 1:
            preset = splt[0][2:]
            prompt = ' '.join(splt[1:])
            if preset in user_prompts.prompts:
                raw = user_prompts.prompts[preset]
                if 'PROMPT' in raw:
                    prompt = re.sub(r'PROMPT', prompt, raw)
                else:
                    prompt = f"{raw} {prompt}"
            else:
                print(f'Prompt preset "{preset}" not found')
                sys.exit(1)

    elif prompt.startswith('-n'):
        create_conv = True

    else:
        break

    prompt_args = prompt_args[1:]

# Setup the request
headers = {
    'Content-Type': 'application/json',
    'User-Agent': target.user_agent,
}
cookies = {data.split('=')[0].strip(): data.split('=')[1].strip() for data in creds.cookies.split(';')}

# Create a new conversation
if create_conv:
    # Post!
    data = {
        "name": ' '.join(prompt_args),
        "uuid": str(uuid.uuid4()),
    }

    print(f"Creating new conversation: {data['name']}")

    response = requests.post(
        url(creds, target.create_conv),
        headers=headers,
        cookies=cookies,
        data=json.dumps(data),
    )
    if response.status_code == 201:
        js = response.json()
        creds.conversation = js['uuid']
        creds.save()
        print(f"New conversation UUID: {creds.conversation}")

        # Delete the parent_uid file
        try:
            os.remove(f'{sys.argv[1]}/parent_uuid')
        except FileNotFoundError:
            pass

    else:
        print(f"Failed to create conversation: {response.status_code}")

# Query LLM
else:
    data = {
        "prompt": ' '.join(prompt_args),
        "parent_message_uuid": parent_uuid,
        "timezone": target.timezone,
        "attachments":[],
        "files":[],
        "rendering_mode":"raw"
    }

    response = requests.post(
        url( creds, target.query_llm ),
        headers=headers,
        cookies=cookies,
        data=json.dumps(data),
        stream=True
    )

    if response.status_code != 200:
        print(f"Failed to query LLM: {response.status_code} {response.text}")
        sys.exit(1)

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


    ### Output Markdown

    print()
    print()

    # Dump in markdown
    console = Console()
    md = Markdown(buffer)
    console.print(md)


    ### Inject commands into history

    # Copy the first code block to the clipboard
    cmds = []
    for token in md.parsed:
        if token.type == 'fence':
            if len(token.content.strip()) != 0:
                cmds.append(token.content.strip())

    home = os.environ.get('HOME')
    with open(f"{home}/.histfile", 'a') as f:
        for idx, cmd in enumerate(reversed(cmds)):
            lines = cmd.strip().split('\n')
            combined = ' \\\n'.join(lines)
            f.write(f": {time.time_ns() // 1000000000}:{idx};{combined}\n")

    ### Save the parent_uuid

    # Query the chat conversation to get the parent_uuid
    response = requests.get(
        url( creds, target.query_conv ),
        headers=headers,
        cookies=cookies,
    )
    if response.status_code == 200:
        js = response.json()
        if 'current_leaf_message_uuid' in js:
            with open(f'{sys.argv[1]}/parent_uuid', 'w') as f:
                f.write( js['current_leaf_message_uuid'])
        else:
            with open(f'{sys.argv[1]}/parent_uuid', 'w') as f:
                f.write( js['uuid'])

        print()
        print(f"{js['name']} conversation length: {len(js['chat_messages'])}")
        print()

    else:
        print(f"Failed to query conversation: {response.status_code}")

