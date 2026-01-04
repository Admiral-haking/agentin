import { useState } from 'react';
import {
  Datagrid,
  List,
  TextField,
  TextInput,
  NumberField,
  TopToolbar,
  useNotify,
  useRefresh,
} from 'react-admin';
import { Button, Stack } from '@mui/material';
import CloudUploadRoundedIcon from '@mui/icons-material/CloudUploadRounded';
import SyncRoundedIcon from '@mui/icons-material/SyncRounded';
import DataObjectRoundedIcon from '@mui/icons-material/DataObjectRounded';
import { ResourceTitle } from '../components/ResourceTitle';
import { TehranDateField } from '../components/TehranDateField';
import { fetchJson } from '../utils/api';

const DEFAULT_API_URL = import.meta.env.DEV
  ? 'http://localhost:8000'
  : 'https://api.teamcore.ir';
const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

const UserListActions = () => {
  const notify = useNotify();
  const refresh = useRefresh();
  const [loading, setLoading] = useState(false);

  const handleSync = async () => {
    setLoading(true);
    try {
      const data = await fetchJson(
        `${API_URL}/admin/users/sync`,
        { method: 'POST' },
        'Sync failed.'
      );
      notify(`Synced: ${data.created} created, ${data.updated} updated`, { type: 'info' });
      refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Sync failed.';
      notify(message, { type: 'warning' });
    } finally {
      setLoading(false);
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await fetchJson(
        `${API_URL}/admin/users/import-csv`,
        {
          method: 'POST',
          body: formData,
        },
        'Import failed.'
      );
      notify(`Imported: ${data.created} created, ${data.updated} updated`, { type: 'info' });
      refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Import failed.';
      notify(message, { type: 'warning' });
    } finally {
      setLoading(false);
      event.target.value = '';
    }
  };

  const handleJsonImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await fetchJson(
        `${API_URL}/admin/users/import-json`,
        {
          method: 'POST',
          body: formData,
        },
        'Import failed.'
      );
      notify(`Imported: ${data.created} created, ${data.updated} updated`, { type: 'info' });
      refresh();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Import failed.';
      notify(message, { type: 'warning' });
    } finally {
      setLoading(false);
      event.target.value = '';
    }
  };

  return (
    <TopToolbar>
      <Stack direction="row" spacing={1}>
        <Button
          variant="outlined"
          startIcon={<SyncRoundedIcon />}
          onClick={handleSync}
          disabled={loading}
        >
          همگام‌سازی دایرکتم
        </Button>
        <Button
          variant="contained"
          component="label"
          startIcon={<CloudUploadRoundedIcon />}
          disabled={loading}
        >
          ورود CSV
          <input type="file" accept=".csv" hidden onChange={handleImport} />
        </Button>
        <Button
          variant="contained"
          color="secondary"
          component="label"
          startIcon={<DataObjectRoundedIcon />}
          disabled={loading}
        >
          ورود JSON
          <input type="file" accept="application/json,.json" hidden onChange={handleJsonImport} />
        </Button>
      </Stack>
    </TopToolbar>
  );
};

const UserFilters = [
  <TextInput key="username" source="username" label="نام کاربری" alwaysOn />,
  <TextInput key="external_id" source="external_id" label="شناسه اینستاگرام" />,
];

export const UserList = () => (
  <List
    filters={UserFilters}
    perPage={25}
    sort={{ field: 'updated_at', order: 'DESC' }}
    actions={<UserListActions />}
    title={<ResourceTitle title="مخاطبین" subtitle="کاربران استخراج‌شده از پیام‌های ورودی." />}
  >
    <Datagrid bulkActionButtons={false}>
      <TextField source="id" label="شناسه" />
      <TextField source="external_id" label="شناسه اینستاگرام" />
      <TextField source="username" label="نام کاربری" />
      <TextField source="follow_status" label="وضعیت فالو" />
      <NumberField source="follower_count" label="تعداد فالوور" />
      <TehranDateField source="created_at" label="اولین مشاهده" showTime />
      <TehranDateField source="updated_at" label="آخرین بروزرسانی" showTime />
    </Datagrid>
  </List>
);
