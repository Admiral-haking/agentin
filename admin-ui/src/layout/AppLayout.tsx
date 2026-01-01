import { Layout } from 'react-admin';
import { AdminAppBar } from './AppBar';
import { AppMenu } from './AppMenu';

export const AppLayout = (props: any) => (
  <Layout {...props} appBar={AdminAppBar} menu={AppMenu} />
);
