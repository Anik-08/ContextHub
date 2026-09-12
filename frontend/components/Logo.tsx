export function LogoMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <div
      className={`flex items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 font-bold text-white shadow-lg shadow-indigo-950/50 ${className}`}
    >
      <span className="text-[length:inherit] text-lg leading-none">C</span>
    </div>
  );
}

export function Logo({
  markClassName,
  showTagline = false,
}: {
  markClassName?: string;
  showTagline?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark className={markClassName ?? "h-9 w-9"} />
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight text-zinc-100">
          Context<span className="text-indigo-400">Hub</span>
        </p>
        {showTagline && (
          <p className="text-[11px] text-zinc-500">
            Knowledge &amp; Code Intelligence
          </p>
        )}
      </div>
    </div>
  );
}