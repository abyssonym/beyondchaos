from dialoguemanager import get_dialogue, set_dialogue
from utils import open_mei_fallback, Substitution, utilrandom as random, POEMS_TABLE


def randomize_poem(fout):
    with open_mei_fallback(POEMS_TABLE) as poems_file:
        poems = []
        wait = 0
        
        current_poem = []
        for line in poems_file:
            line = line.split('#')[0].strip()

            if not line:
                if current_poem:
                    current_poem.append("<wait 390 frames><wait 1 frame><page>")
                    wait += 1
                continue
            
            if line.startswith("---") and current_poem:
                current_poem.append("<wait 390 frames><wait 1 frame>")
                wait += 1
                poems.append("".join(current_poem))
                current_poem = []
                continue
            
            if not line.endswith("<line>"):
                line = line + "<line>"
            current_poem.append(line)
        
        text = random.choice(poems)
        print(text)
        set_dialogue(0x9FC, text)

        wait = max(wait * 26 + 2, 255)
        # Adjust wait to be long enough for the poem
        # TODO: change wait based on selected poem
        wait_sub = Substitution()
        wait_sub.set_location(0xC401D)
        wait_sub.bytestring = bytes([0xB5, wait])
        wait_sub.write(fout)
