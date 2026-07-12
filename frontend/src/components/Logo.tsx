interface Props {
  className?: string;
}

// kgent's mark, drawn in currentColor so it can inherit the accent or ink color.
export default function Logo({ className }: Props) {
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <rect x="40" y="32" width="20" height="136" fill="currentColor" />
      <g fill="none" stroke="currentColor" strokeWidth="22" strokeLinecap="square">
        <polyline points="70,100 130,40 170,40" />
        <polyline points="70,100 130,160 170,160" />
      </g>
    </svg>
  );
}
