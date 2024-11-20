from git import Repo, Actor
import os
import requests
from markdownify import markdownify
from tqdm import tqdm
from unidecode import unidecode
import regex as re
import shutil
from bs4 import BeautifulSoup

def get_page_ids():
    r = requests.get("https://www.auswaertiges-amt.de/opendata/travelwarning/").json()
    return r["response"]["contentList"]

def get_page(pid):
    r = requests.get(f"https://www.auswaertiges-amt.de/opendata/travelwarning/{pid}").json()
    return r["response"][pid]

def get_all_pages():
    return [get_page(i) for i in tqdm(get_page_ids())]

def to_markdown(html):
    md = re.sub(r"\n\s*\n\s*", "\n\n", markdownify(html, heading_style="ATX")).strip() + "\n"
    return re.sub(r"(\*\*)+", "**", md)


def write_with_tracking(filename, name, content, track_changes):
    if not os.path.exists(filename):
        track_changes(name, "hinzugefügt")
    elif open(filename, "r").read() != content:
        track_changes(name, "geändert")

    with open(filename, "w") as f:
        f.write(content)


def save_general_info(p, track_changes):
    disclaimer = to_markdown(p["disclaimer"])
    write_with_tracking("Haftungsausschluss.md", "Haftungsausschluss", disclaimer, track_changes)

    soup = BeautifulSoup(p["content"], features="html.parser")
    infobox = soup.find(string=re.compile("Lagen können sich schnell verändern und entwickeln. Wir empfehlen Ihnen:")).parent.parent

    write_with_tracking("AllgemeineEmpfehlung.md", "Allgemeine Empfehlung", "# Allgemeine Empfehlung\n\n" + to_markdown(str(infobox)), track_changes)

    furtherInfoHead = soup.find(string="Weitere Hinweise für Ihre Reise").parent
    furtherInfo = furtherInfoHead.next_sibling

    write_with_tracking("WeitereHinweise.md", "Weitere Hinweise für Ihre Reise", "# Weitere Hinweise für Ihre Reise\n\n" + to_markdown(str(furtherInfo)), track_changes)

def to_filename(n):
    filesafe = re.sub(r"[^\p{L} ]", "", n.lower())
    camel_case = "".join(w.capitalize() for w in filesafe.split())
    return camel_case + ".md"

def create_content(p):
    soup = BeautifulSoup(p["content"], features="html.parser") 
    infobox = soup.find(string=re.compile("Lagen können sich schnell verändern und entwickeln. Wir empfehlen Ihnen:")).parent.parent
    infobox.clear()

    furtherInfoHead = soup.find(string="Weitere Hinweise für Ihre Reise").parent
    furtherInfo = furtherInfoHead.next_sibling
    furtherInfoHead.extract()
    furtherInfo.extract()

    md_body = to_markdown(str(soup))

    md = f"# {p['title']}\n\n{md_body}"

    return md


def save_page(filename, p, track_changes):
    os.makedirs("countries", exist_ok=True)
    content = create_content(p)
    path = "countries/" + filename
    if not os.path.exists(path):
        track_changes(p["countryName"], "hinzugefügt")
    elif open(path, "r").read() != content:
        track_changes(p["countryName"], "geändert", p["lastChanges"])

    with open(path, "w") as f:
        f.write(content)

def to_commitmessage(changes):
    title = ", ".join(f"{c['name']} {c['action']}" for c in changes)

    body = "\n\n".join(c["name"] + ":\n" + to_markdown(c['changelog']).replace("Letzte Änderungen:", "").strip() for c in changes if c["changelog"])

    return title + "\n\n" + body

def save_all():
    if os.path.exists("countries"):
        unseen = set(os.listdir("countries"))
    else:
        unseen = set()
    changes = []
    def track_changes(name, action, changelog=None):
        changes.append({"name": name, "action": action, "changelog": changelog})

    pages = get_all_pages()
    save_general_info(pages[0], track_changes)
    for p in pages:
        filename = to_filename(p["countryName"])
        save_page(filename, p, track_changes)
        unseen.discard(filename)

    for u in unseen:
        track_changes(u, "entfernt")
        os.remove("countries/" + u)


    cm = to_commitmessage(changes)

    print("Commit message:")
    print(cm)

    if not os.environ.get("NO_COMMIT") and len(changes) > 0:
        repo = Repo()
        actor = Actor("ReisehinweisBot", "reisehinweis.web@lbroe.de")
        repo.git.add(all=True)
        repo.index.commit(cm, author=actor, committer=actor)
        repo.remote(name="origin").push()
        print("Pushed.")

if __name__ == "__main__":
    save_all()
