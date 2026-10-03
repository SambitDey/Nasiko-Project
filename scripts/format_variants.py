import json, tiktoken
enc = tiktoken.get_encoding("o200k_base")
d = json.load(open("/home/sdey/work-2026-10-03/reference/compact-tools-eval.json"))
tools = {t["function"]["name"]: t for t in d["tools"]}
SYS = "Today is 2026-10-02, timezone Asia/Kolkata."
def T(o, pretty): return len(enc.encode(json.dumps(o, ensure_ascii=False, separators=None if pretty else (",",":"))))
F = {
"brief_arrow": ({
 "create_calendar_event":"create_calendar_event(title:str # Event title, start:datetime # Start time, ISO 8601, duration_min?:int # Duration in minutes, attendees?:[str] # Attendee emails, visibility?:public|private) - Create an event in the user's calendar.",
 "send_email":"send_email(to:[str] # Recipient emails, subject:str # Subject line, body:str # Plain-text body, cc?:[str] # CC emails) - Send an email from the user's account."},
 "Tools:\n{d}\nTo call a tool, emit: <<call name {{json args}}>>"),
"typescript": ({
 "create_calendar_event":"// Create an event in the user's calendar.\ncreate_calendar_event(a:{title:string /*Event title*/; start:string /*date-time, ISO 8601*/; duration_min?:integer /*minutes*/; attendees?:string[] /*emails*/; visibility?:'public'|'private'})",
 "send_email":"// Send an email from the user's account.\nsend_email(a:{to:string[] /*emails*/; subject:string; body:string /*plain text*/; cc?:string[] /*emails*/})"},
 "Tools:\n{d}\nTo call a tool, emit: <<call name {{json args}}>>"),
"lean_lossy": ({
 "create_calendar_event":"create_calendar_event(title,start:datetime,duration_min?:int,attendees?:[email],visibility?:public|private) Create calendar event",
 "send_email":"send_email(to:[email],subject,body,cc?:[email]) Send email"},
 "Tools:\n{d}\nCall: <<call name {{json}}>>"),
}
for pretty in (False, True):
  for name,(c,I) in F.items():
    bt=ct=0
    for k in d["cases"]:
      m=[{"role":"system","content":SYS}]+k["messages"]
      bt+=T({"model":"m","messages":m,"tools":[tools[n] for n in k["tools"]]},pretty)
      ct+=T({"model":"m","messages":[{"role":"system","content":SYS+"\n"+I.format(d="\n".join(c[n] for n in k["tools"]))}]+k["messages"]},pretty)
    print("pretty" if pretty else "compact", f"{name:12}", bt, ct, f"{1-ct/bt:.1%}")
