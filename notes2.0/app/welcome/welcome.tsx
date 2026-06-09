import { Button } from "~/components/ui/button"

export default function Welcome() {
  const notes = [
  { text: "Meeting notes from standup", time: "9:14 am" },
  { text: "Ideas for the side project",  time: "Yesterday" },
  { text: "Book list for summer",         time: "Mon" },
  { text: "New thoughts!", time:"Last Week"}
];
  return (
    <section className="flex flex-col items-center text-center px-6 py-20 w-full">
      <div className="text-xs font-medium tracking-widest text-slate-400 uppercase mb-5">Notes. process. fast. analytics.</div>
      <h1 className="text-5xl font-bold tracking-tight text-slate-900 max-w-xl leading-tight mb-4">Hi Timothy! <br/> What's on your mind?</h1>
      <p className="text-lg text-slate-500 max-w-sm leading-relaxed mb-7">Capture your thoughts quickly and effectively. I think you're doing well but might need some time to think about some things. This will eventually be rapidly generated.</p>
      <div className="flex gap-3 mb">
        <Button variant="default" size="lg">Capture a Thought</Button>
        <Button variant="secondary" size="lg">View Analytics</Button>
      </div>
      <div className="mt-12 w-full max-w-sm rounded-2xl border border-slate-100 bg-white shadow-sm p-5 text-left">
        <p className="text-xs text-slate-400 uppercase tracking-widest mb-4">For you</p>
        {notes.map(({ text, time }) => (
          <Button variant="ghost" key={text} className="flex items-center gap-3 py-2.5 last:border-0">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-300 shrink-0" />
            <span className="text-sm text-slate-700 flex-1">{text}</span>
            <span className="text-xs text-slate-400">{time}</span>
          </Button>
        ))}
      </div>

      <div className="mt-8 text-xs text-slate-400"> pick up where you left off </div>
      

    </section>
  );
}