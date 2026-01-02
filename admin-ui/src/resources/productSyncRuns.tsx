import {
  Datagrid,
  DateField,
  List,
  NumberField,
  TextField,
} from 'react-admin';
import { Stack, Tabs, Tab } from '@mui/material';
import { Link, useLocation } from 'react-router-dom';
import { ResourceTitle } from '../components/ResourceTitle';

const ProductsHeader = () => {
  const location = useLocation();
  const tabValue = location.pathname.includes('product-sync-runs') ? 1 : 0;
  return (
    <Stack spacing={2}>
      <ResourceTitle
        title="محصولات"
        subtitle="کاتالوگ همگام با فروشگاه و توروب."
        tag="کاتالوگ"
      />
      <Tabs value={tabValue} textColor="primary" indicatorColor="primary">
        <Tab label="محصولات" component={Link} to="/products" />
        <Tab label="گزارش همگام‌سازی" component={Link} to="/product-sync-runs" />
      </Tabs>
    </Stack>
  );
};

export const ProductSyncRunList = () => (
  <List
    title={<ProductsHeader />}
    sort={{ field: 'started_at', order: 'DESC' }}
  >
    <Datagrid>
      <TextField source="id" label="شناسه" />
      <TextField source="status" label="وضعیت" />
      <NumberField source="created_count" label="جدید" />
      <NumberField source="updated_count" label="آپدیت" />
      <NumberField source="unchanged_count" label="بدون تغییر" />
      <NumberField source="torob_count" label="توروب" />
      <NumberField source="sitemap_count" label="سایت‌مپ" />
      <NumberField source="error_count" label="خطاها" />
      <DateField source="started_at" label="شروع" showTime />
      <DateField source="finished_at" label="پایان" showTime />
      <TextField source="error_message" label="پیام خطا" />
    </Datagrid>
  </List>
);
