import { FunctionalComponent, reactive } from 'vue';

interface ConfirmOptions {
  title?: string;
  message: string;
  icon?: FunctionalComponent;
  closeable?: boolean;
  showRememberChoice?: boolean;
  acceptButton?: {
    label: string;
    variant?: 'primary' | 'default' | 'text' | 'danger'
    icon?: string;
    onClick?: () => void;
    position?: 'left' | 'center' | 'right';
  };
  rejectButton?: {
    label: string;
    icon?: string;
    onClick?: () => void;
    position?: 'left' | 'center' | 'right';
  };
  buttons?: Array<{
    label: string;
    icon?: string;
    onClick: () => void;
    position?: 'left' | 'center' | 'right';
  }>;
}

export const confirmState = reactive<
  ConfirmOptions & {
    visible: boolean;
    resolve?: (value: boolean, rememberChoice?: boolean) => void;
  }
>({
  visible: false,
  message: ''
});

function resetState() {
  confirmState.title = undefined;
  confirmState.message = '';
  confirmState.icon = undefined;
  confirmState.closeable = true;
  confirmState.showRememberChoice = false;
  confirmState.acceptButton = undefined;
  confirmState.rejectButton = undefined;
  confirmState.buttons = undefined;
  confirmState.resolve = undefined;
}

export function useConfirm() {
  async function confirm(
    options: ConfirmOptions
  ): Promise<{ confirmed: boolean; rememberChoice: boolean }> {
    resetState();

    return new Promise((resolve) => {
      confirmState.visible = true;
      confirmState.title = options.title;
      confirmState.message = options.message;
      confirmState.icon = options.icon;
      confirmState.closeable = options.closeable ?? true;
      confirmState.showRememberChoice = options.showRememberChoice ?? false;
      confirmState.acceptButton = options.acceptButton ?? { label: 'OK' };
      confirmState.rejectButton = options.rejectButton ?? { label: 'Cancel' };
      confirmState.buttons = options.buttons;

      confirmState.resolve = (confirmed: boolean, rememberChoice = false) => {
        confirmState.visible = false;
        resolve({ confirmed, rememberChoice });
      };
    });
  }

  return { confirm, confirmState };
}