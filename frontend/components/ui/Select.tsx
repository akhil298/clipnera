"use client";
import React, { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, ChevronDown } from 'lucide-react';

export interface SelectOption<T extends string | number> {
  value: T;
  label: string;
  disabled?: boolean;
  /** Options sharing a group render under one heading; keep them adjacent. */
  group?: string;
  title?: string;
}

interface SelectProps<T extends string | number> {
  value: T | undefined;
  options: SelectOption<T>[];
  onChange: (value: T) => void;
  /** Trigger styling; carries the field's size, border and colours. */
  className?: string;
  /** Shown when `value` matches no option. */
  placeholder?: string;
  'aria-label'?: string;
}

const MENU_GAP = 4;
const MENU_MAX_HEIGHT = 240;

interface MenuPosition {
  left: number;
  width: number;
  top?: number;
  bottom?: number;
}

/**
 * Dropdown whose list always opens attached to the field. Native `<select>`
 * popups are drawn by the OS, and on macOS they cover the field centred on the
 * selected option instead of dropping below it.
 */
export function Select<T extends string | number>({
  value,
  options,
  onChange,
  className = '',
  placeholder = 'Select…',
  'aria-label': ariaLabel,
}: SelectProps<T>) {
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [position, setPosition] = useState<MenuPosition | null>(null);

  const selectedIndex = options.findIndex((option) => option.value === value);
  const selected = options[selectedIndex];

  const place = useCallback(() => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const spaceBelow = window.innerHeight - rect.bottom;
    const openUp = spaceBelow < MENU_MAX_HEIGHT && rect.top > spaceBelow;
    setPosition(
      openUp
        ? { left: rect.left, width: rect.width, bottom: window.innerHeight - rect.top + MENU_GAP }
        : { left: rect.left, width: rect.width, top: rect.bottom + MENU_GAP },
    );
  }, []);

  const close = useCallback(() => {
    setOpen(false);
    setPosition(null);
  }, []);

  const openMenu = () => {
    place();
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : options.findIndex((option) => !option.disabled));
    setOpen(true);
  };

  const choose = (index: number) => {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    close();
    triggerRef.current?.focus();
  };

  const step = (from: number, direction: 1 | -1) => {
    for (let i = from + direction; i >= 0 && i < options.length; i += direction) {
      if (!options[i].disabled) return i;
    }
    return from;
  };

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target)) close();
    };
    // Capture catches scrolling in any ancestor, not just the window.
    const onScroll = (event: Event) => {
      if (!menuRef.current?.contains(event.target as Node)) place();
    };
    document.addEventListener('mousedown', onPointerDown);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', place);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', place);
    };
  }, [open, close, place]);

  useLayoutEffect(() => {
    if (open && activeIndex >= 0) {
      menuRef.current?.querySelector(`[data-index="${activeIndex}"]`)?.scrollIntoView({ block: 'nearest' });
    }
  }, [open, activeIndex]);

  const onKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(event.key)) {
        event.preventDefault();
        openMenu();
      }
      return;
    }
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        setActiveIndex((index) => step(index, 1));
        break;
      case 'ArrowUp':
        event.preventDefault();
        setActiveIndex((index) => step(index, -1));
        break;
      case 'Home':
        event.preventDefault();
        setActiveIndex(step(-1, 1));
        break;
      case 'End':
        event.preventDefault();
        setActiveIndex(step(options.length, -1));
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        choose(activeIndex);
        break;
      case 'Escape':
        event.preventDefault();
        close();
        break;
      case 'Tab':
        close();
        break;
    }
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={`${id}-listbox`}
        aria-activedescendant={open && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
        aria-label={ariaLabel}
        title={selected?.title}
        onClick={() => (open ? close() : openMenu())}
        onKeyDown={onKeyDown}
        className={`flex items-center justify-between gap-2 text-left cursor-pointer ${className}`}
      >
        <span className={`truncate ${selected ? '' : 'text-neutral-500'}`}>{selected?.label ?? placeholder}</span>
        <ChevronDown
          className={`w-3.5 h-3.5 shrink-0 text-neutral-400 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open &&
        position &&
        createPortal(
          <ul
            ref={menuRef}
            id={`${id}-listbox`}
            role="listbox"
            aria-label={ariaLabel}
            style={{ ...position, minWidth: position.width, width: 'max-content', maxWidth: 'min(24rem, calc(100vw - 16px))', maxHeight: MENU_MAX_HEIGHT }}
            className="fixed z-[1000] overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-950 p-1 shadow-2xl shadow-black/50 animate-in fade-in duration-100"
          >
            {options.map((option, index) => {
              const isSelected = index === selectedIndex;
              const showGroup = option.group && option.group !== options[index - 1]?.group;
              return (
                <React.Fragment key={`${option.group ?? ''}:${option.value}`}>
                  {showGroup && (
                    <li
                      role="presentation"
                      className="px-2.5 pt-2 pb-1 text-[10px] font-bold uppercase tracking-wider text-neutral-500"
                    >
                      {option.group}
                    </li>
                  )}
                  <li
                    id={`${id}-option-${index}`}
                    data-index={index}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={option.disabled}
                    title={option.title}
                    onMouseEnter={() => !option.disabled && setActiveIndex(index)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => choose(index)}
                    className={`flex items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-xs ${
                      option.disabled
                        ? 'cursor-not-allowed text-neutral-600'
                        : `cursor-pointer ${index === activeIndex ? 'bg-neutral-800 text-white' : 'text-neutral-300'}`
                    } ${isSelected ? 'font-semibold text-amber-400' : ''}`}
                  >
                    <span className="truncate">{option.label}</span>
                    {isSelected && <Check className="w-3.5 h-3.5 shrink-0 text-amber-400" />}
                  </li>
                </React.Fragment>
              );
            })}
          </ul>,
          document.body,
        )}
    </>
  );
}
