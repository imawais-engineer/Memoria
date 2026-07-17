import { useEffect, useRef, useState } from 'react'

export default function ModelDropdown({ options, value, onChange, disabled = false }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  const selected = options.find((opt) => opt.id === value) || options[0]

  useEffect(() => {
    function handleClickOutside(e) {
      if (!rootRef.current?.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function pick(id) {
    onChange(id)
    setOpen(false)
  }

  return (
    <div className="model-dropdown" ref={rootRef}>
      <button
        type="button"
        className={`model-dropdown-trigger${open ? ' open' : ''}`}
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="model-dropdown-label">{selected?.name || 'Select model'}</span>
        <span className="model-dropdown-chevron" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        <ul className="model-dropdown-menu" role="listbox">
          {options.map((opt) => (
            <li key={opt.id}>
              <button
                type="button"
                role="option"
                aria-selected={opt.id === value}
                className={`model-dropdown-option${opt.id === value ? ' selected' : ''}`}
                onClick={() => pick(opt.id)}
              >
                {opt.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
