const SIZES = {
  xs: 24,
  sm: 28,
  md: 36,
  lg: 44,
  xl: 56,
}

export default function MemoriaLogo({
  size = 'md',
  showName = false,
  tagline = null,
  className = '',
  nameClassName = '',
}) {
  const dim = SIZES[size] || SIZES.md
  const fontSize = Math.round(dim * 0.48)

  return (
    <div className={`memoria-logo ${className}`.trim()}>
      <svg
        className="memoria-logo-mark"
        width={dim}
        height={dim}
        viewBox="0 0 40 40"
        fill="none"
        aria-hidden="true"
      >
        <defs>
          <filter id="memoria-logo-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <linearGradient id="memoria-logo-bg" x1="4" y1="4" x2="36" y2="36">
            <stop offset="0%" stopColor="#1c2140" />
            <stop offset="100%" stopColor="#121528" />
          </linearGradient>
        </defs>
        <rect
          x="2"
          y="2"
          width="36"
          height="36"
          rx="10"
          fill="url(#memoria-logo-bg)"
          stroke="rgba(108, 140, 255, 0.35)"
          strokeWidth="1"
        />
        <text
          x="20"
          y="27"
          textAnchor="middle"
          fill="#6c8cff"
          fontFamily="inherit"
          fontSize={fontSize}
          fontWeight="700"
          filter="url(#memoria-logo-glow)"
        >
          M
        </text>
      </svg>
      {(showName || tagline) && (
        <div className="memoria-logo-text">
          {showName && (
            <span className={`memoria-logo-name ${nameClassName}`.trim()}>Memoria</span>
          )}
          {tagline && <span className="memoria-logo-tagline">{tagline}</span>}
        </div>
      )}
    </div>
  )
}
