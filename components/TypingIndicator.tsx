export function TypingIndicator() {
  return (
    <div className="flex w-full justify-start mb-4">
      <div className="bg-slate-100 border border-slate-200 rounded-2xl px-4 py-3">
        <div className="flex gap-1">
          <div
            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
            style={{ animationDelay: '0ms' }}
          />
          <div
            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
            style={{ animationDelay: '150ms' }}
          />
          <div
            className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
            style={{ animationDelay: '300ms' }}
          />
        </div>
      </div>
    </div>
  );
}
