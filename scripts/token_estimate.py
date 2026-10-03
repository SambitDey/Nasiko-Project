import json, tiktoken
enc = tiktoken.get_encoding("o200k_base")
d = json.load(open("/home/sdey/work-2026-10-03/reference/compact-tools-eval.json"))
tools = {t["function"]["name"]: t for t in d["tools"]}
SYS = "Today is 2026-10-02, timezone Asia/Kolkata."
def T(o): return len(enc.encode(json.dumps(o, ensure_ascii=False)))
V = {
 "A_desc_kept": ({
  "create_calendar_event": "create_calendar_event(title:str # Event title, start:datetime # Start time ISO 8601, duration_min?:int # Duration in minutes, attendees?:[str] # Attendee emails, visibility?:public|private): Create an event in the user's calendar.",
  "send_email": "send_email(to:[str] # Recipient emails, subject:str # Subject line, body:str # Plain-text body, cc?:[str] # CC emails): Send an email from the user's account."},
  "Tools:\n{defs}\nCall: <<call NAME {{json args}}>>"),
 "B_redundant_desc_dropped": ({
  "create_calendar_event": "create_calendar_event(title:str, start:datetime, duration_min?:int, attendees?:[str] emails, visibility?:public|private): Create an event in the user's calendar.",
  "send_email": "send_email(to:[str] emails, subject:str, body:str plain text, cc?:[str] emails): Send an email from the user's account."},
  "Tools:\n{defs}\nCall: <<call NAME {{json args}}>>"),
}
for name,(compact,INSTR) in V.items():
  bt=ct=0
  for c in d["cases"]:
    m=[{"role":"system","content":SYS}]+c["messages"]
    b=T({"model":"m","messages":m,"tools":[tools[n] for n in c["tools"]]})
    k=T({"model":"m","messages":[{"role":"system","content":SYS+"\n"+INSTR.format(defs="\n".join(compact[n] for n in c["tools"]))}]+c["messages"]})
    bt+=b;ct+=k
  print(name,bt,ct,f"{1-ct/bt:.1%}")
# what's the floor: request with no tools at all
bt=sum(T({"model":"m","messages":[{"role":"system","content":SYS}]+c["messages"],"tools":[tools[n] for n in c["tools"]]}) for c in d["cases"])
nt=sum(T({"model":"m","messages":[{"role":"system","content":SYS}]+c["messages"]}) for c in d["cases"])
print("baseline",bt,"no-tools floor",nt,"max possible saving",f"{1-nt/bt:.1%}")
