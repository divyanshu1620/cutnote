import React from 'react';
import { cn } from '../../lib/utils';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
}

export function Button({ className, variant = 'primary', size = 'md', ...props }: ButtonProps) {
  const baseStyles = "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-cobalt disabled:pointer-events-none disabled:opacity-50";
  
  const variants = {
    primary: "bg-primary text-canvas hover:bg-primary/90",
    secondary: "bg-input text-primary border border-hairline hover:bg-hairline",
    danger: "bg-red-900/20 text-red-400 border border-red-900/50 hover:bg-red-900/30",
    ghost: "text-muted hover:text-primary hover:bg-input",
  };

  const sizes = {
    sm: "h-8 px-3 text-xs",
    md: "h-10 px-4 text-sm",
    lg: "h-12 px-6 text-base",
  };

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      {...props}
    />
  );
}