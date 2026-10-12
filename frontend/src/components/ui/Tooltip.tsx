import {
  cloneElement,
  isValidElement,
  useId,
  useRef,
  useState,
  type FocusEvent,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from "react";

type Props = {
  label: string;
  children: ReactElement;
  delayMs?: number;
};

export function Tooltip({ label, children, delayMs = 400 }: Props) {
  const id = useId();
  const timer = useRef<number | null>(null);
  const [open, setOpen] = useState(false);

  function show() {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setOpen(true), delayMs);
  }

  function hide() {
    if (timer.current) window.clearTimeout(timer.current);
    setOpen(false);
  }

  function onMouseEnter(e: MouseEvent) {
    show();
    children.props.onMouseEnter?.(e);
  }

  function onMouseLeave(e: MouseEvent) {
    hide();
    children.props.onMouseLeave?.(e);
  }

  function onFocus(e: FocusEvent) {
    show();
    children.props.onFocus?.(e);
  }

  function onBlur(e: FocusEvent) {
    hide();
    children.props.onBlur?.(e);
  }

  if (!isValidElement(children)) return children as ReactNode;

  type TriggerProps = {
    onMouseEnter?: (e: MouseEvent) => void;
    onMouseLeave?: (e: MouseEvent) => void;
    onFocus?: (e: FocusEvent) => void;
    onBlur?: (e: FocusEvent) => void;
    "aria-describedby"?: string;
  };

  const trigger = cloneElement(children as ReactElement<TriggerProps>, {
    onMouseEnter,
    onMouseLeave,
    onFocus,
    onBlur,
    "aria-describedby": open ? id : undefined,
  });

  return (
    <span className="aq-tooltip-wrap inline-flex">
      {trigger}
      {open ? (
        <span id={id} role="tooltip" className="aq-tooltip-bubble">
          {label}
        </span>
      ) : null}
    </span>
  );
}
