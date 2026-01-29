import { Alert, AlertTitle } from '@mui/material';

type InlineAlertProps = {
  message: string;
  title?: string;
  severity?: 'error' | 'warning' | 'info' | 'success';
};

export const InlineAlert = ({
  message,
  title = 'خطا',
  severity = 'error',
}: InlineAlertProps) => (
  <Alert
    severity={severity}
    variant="outlined"
    sx={{
      borderRadius: 2,
      bgcolor: 'rgba(255, 255, 255, 0.92)',
      borderColor: 'rgba(18, 22, 33, 0.12)',
      boxShadow: '0 12px 24px rgba(18, 22, 33, 0.08)',
      '& .MuiAlert-icon': { alignItems: 'center' },
    }}
  >
    {title ? <AlertTitle sx={{ fontWeight: 700 }}>{title}</AlertTitle> : null}
    {message}
  </Alert>
);
