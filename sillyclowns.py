from dialoguemanager import get_dialogue, set_dialogue
from utils import open_mei_fallback, Substitution, utilrandom as random, PASSWORDS_TABLE, POEMS_TABLE


POEM_PAGE_BREAK = "<wait 390 frames><wait 1 frame><page>"


def randomize_poem(fout):
    poems = []

    with open_mei_fallback(POEMS_TABLE, encoding='utf8') as poems_file:
        current_poem = []
        page_break = False
        wait = 0
        for line in poems_file:
            line = line.split('#')[0].strip()

            if not line:
                if current_poem:
                    page_break = True
                continue

            if line.startswith("---") and current_poem:
                current_poem.append("<wait 390 frames><wait 1 frame>")
                wait += 1
                poems.append(("".join(current_poem), wait))
                current_poem = []
                page_break = False
                wait = 0
                continue

            if page_break:
                current_poem.append(POEM_PAGE_BREAK)
                wait += 1
                page_break = False
            elif current_poem:
                current_poem.append("<line>")
            current_poem.append(line)

    if not poems:
        return

    text, wait = random.choice(poems)
    set_dialogue(0x9FC, text)
    wait = min(wait * 26 + 2, 255)

    # Adjust wait to be long enough for the poem
    wait_sub = Substitution()
    wait_sub.set_location(0xC401D)
    wait_sub.bytestring = bytes([0xB5, wait])
    wait_sub.write(fout)

def randomize_passwords():
    passwords = [[], [], []]

    with open_mei_fallback(PASSWORDS_TABLE) as passwords_file:
        i = 0
        for line in passwords_file:
            line = line.split('#')[0].strip()

            if not line:
                continue

            if line.startswith("------") and i < len(passwords) - 1:
                i += 1
                continue

            passwords[i].append(line)

    if all(passwords):
        text = get_dialogue(0xE0)
        text = text.replace("Rose bud", random.choice(passwords[0]))
        text = text.replace("Courage", random.choice(passwords[1]))
        text = text.replace("Failure", random.choice(passwords[2]))

        set_dialogue(0xE0, text)
