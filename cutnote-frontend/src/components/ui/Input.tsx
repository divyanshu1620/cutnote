import React from 'react';
import { cn } from '../../lib/utils';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        "flex h-10 w-full rounded-md border border-hairline bg-input px-3 py-2 text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cobalt disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}

interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {}

export function TextArea({ className, ...props }: TextAreaProps) {
  return (
    <textarea
      className={cn(
        "flex min-h-[80px] w-full rounded-md border border-hairline bg-input px-3 py-2 text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cobalt disabled:cursor-not-allowed disabled:opacity-50 resize-none",
        className
      )}
      {...props}
    />
  );
}