'use client';

import React, { useState, useEffect } from 'react';

interface CollapsibleCardProps {
  title: string;
  subtitle?: string;
  icon?: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  storageKey?: string;
  variant?: 'default' | 'accent';
}

export function CollapsibleCard({
  title,
  subtitle,
  icon,
  badge,
  children,
  defaultOpen = false,
  storageKey,
  variant = 'default',
}: CollapsibleCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  // Load state from localStorage on mount
  useEffect(() => {
    if (storageKey) {
      const saved = localStorage.getItem(storageKey);
      if (saved !== null) {
        setOpen(JSON.parse(saved));
      }
    }
  }, [storageKey]);

  // Save state to localStorage on change
  const handleToggle = () => {
    const newState = !open;
    setOpen(newState);
    if (storageKey) {
      localStorage.setItem(storageKey, JSON.stringify(newState));
    }
  };

  const headerBg = variant === 'accent' ? '#0d0d18' : '#0a0a14';
  const contentBg = '#07070f';

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: '1px solid #1e1e2a' }}
    >
      {/* Header / Toggle Button */}
      <button
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-4 py-3 hover:opacity-90 transition-colors text-left"
        style={{ background: headerBg }}
        aria-expanded={open}
        aria-label={`${open ? 'Close' : 'Open'} ${title}`}
      >
        {/* Left: Icon + Title + Subtitle */}
        <div className="flex items-center gap-3 flex-1">
          {icon && <span className="text-lg flex-shrink-0">{icon}</span>}
          <div className="min-w-0">
            <p className="text-xs font-bold text-white truncate">{title}</p>
            {subtitle && (
              <p className="text-[10px] text-gray-500 mt-0.5 truncate">
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Right: Badge + Chevron */}
        <div className="flex items-center gap-3 flex-shrink-0 ml-3">
          {badge && <div className="flex-shrink-0">{badge}</div>}
          <svg
            className={`w-5 h-5 flex-shrink-0 transition-transform ${
              open ? 'rotate-180' : ''
            }`}
            style={{ color: '#9ca3af' }}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
        </div>
      </button>

      {/* Content */}
      {open && (
        <div className="px-4 py-4" style={{ background: contentBg }}>
          {children}
        </div>
      )}
    </div>
  );
}
