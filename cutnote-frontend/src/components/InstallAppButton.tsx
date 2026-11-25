import React, { useEffect, useState } from 'react';
import { Download, Check } from 'lucide-react';
import { Button } from './ui/Button';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

export const InstallAppButton: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    const standalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      Boolean((window.navigator as any).standalone);
    if (standalone) {
      setIsInstalled(true);
    }

    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    const onAppInstalled = () => {
      setIsInstalled(true);
      setDeferredPrompt(null);
    };

    window.addEventListener('beforeinstallprompt', onBeforeInstall);
    window.addEventListener('appinstalled', onAppInstalled);

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall);
      window.removeEventListener('appinstalled', onAppInstalled);
    };
  }, []);

  if (isInstalled) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-md border border-hairline bg-input px-2.5 py-1 text-xs text-muted">
        <Check className="h-3.5 w-3.5 text-green-400" strokeWidth={1.5} />
        App Installed
      </span>
    );
  }

  if (!deferredPrompt) {
    return null;
  }

  const handleInstall = async () => {
    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    if (choice.outcome === 'accepted') {
      setDeferredPrompt(null);
    }
  };

  return (
    <Button variant="secondary" size="sm" onClick={handleInstall}>
      <Download className="mr-1.5 h-3.5 w-3.5" strokeWidth={1.5} />
      Install CutNote
    </Button>
  );
};
