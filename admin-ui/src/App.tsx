import { Admin, CustomRoutes, Resource } from 'react-admin';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import ForumRoundedIcon from '@mui/icons-material/ForumRounded';
import MessageRoundedIcon from '@mui/icons-material/MessageRounded';
import QuizRoundedIcon from '@mui/icons-material/QuizRounded';
import Inventory2RoundedIcon from '@mui/icons-material/Inventory2Rounded';
import SyncAltRoundedIcon from '@mui/icons-material/SyncAltRounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import AnalyticsRoundedIcon from '@mui/icons-material/AnalyticsRounded';
import PeopleAltRoundedIcon from '@mui/icons-material/PeopleAltRounded';
import SupportAgentRoundedIcon from '@mui/icons-material/SupportAgentRounded';
import ScheduleRoundedIcon from '@mui/icons-material/ScheduleRounded';
import { Route } from 'react-router-dom';
import { authProvider } from './authProvider';
import { dataProvider } from './dataProvider';
import { CampaignCreate, CampaignEdit, CampaignList } from './resources/campaigns';
import { FaqCreate, FaqEdit, FaqList } from './resources/faqs';
import { ProductCreate, ProductEdit, ProductList } from './resources/products';
import { ProductSyncRunList } from './resources/productSyncRuns';
import { ConversationList } from './resources/conversations';
import { MessageList } from './resources/messages';
import { SettingsEdit, SettingsList } from './resources/settings';
import { LogList } from './resources/logs';
import { UserEdit, UserList } from './resources/users';
import { TicketEdit, TicketList } from './resources/tickets';
import { FollowupEdit, FollowupList } from './resources/followups';
import { AppLayout } from './layout/AppLayout';
import { Dashboard } from './Dashboard';
import { appTheme } from './theme';
import { AssistantPage } from './pages/AssistantPage';
import { AssistantActionsPage } from './pages/AssistantActionsPage';
import { DirectamConsole } from './pages/DirectamConsole';
import { HealthPage } from './pages/HealthPage';
import { UserBehaviorPage } from './pages/UserBehaviorPage';
import { AiContextPage } from './pages/AiContextPage';

const productsEnabled = (import.meta.env.VITE_PRODUCTS_ENABLED || 'false') === 'true';

export const App = () => (
  <Admin
    dataProvider={dataProvider}
    authProvider={authProvider}
    requireAuth
    layout={AppLayout}
    dashboard={Dashboard}
    theme={appTheme}
  >
    {permissions => (
      <>
        <CustomRoutes>
          <Route path="/assistant" element={<AssistantPage />} />
          <Route path="/assistant/actions" element={<AssistantActionsPage />} />
          <Route path="/directam" element={<DirectamConsole />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="/behavior" element={<UserBehaviorPage />} />
          <Route path="/ai-context" element={<AiContextPage />} />
        </CustomRoutes>
        <Resource
          name="campaigns"
          list={CampaignList}
          edit={CampaignEdit}
          create={CampaignCreate}
          icon={CampaignRoundedIcon}
          options={{ label: 'Campaigns' }}
        />
        <Resource
          name="faqs"
          list={FaqList}
          edit={FaqEdit}
          create={FaqCreate}
          icon={QuizRoundedIcon}
          options={{ label: 'FAQs' }}
        />
        {productsEnabled && permissions === 'admin' && (
          <Resource
            name="products"
            list={ProductList}
            edit={ProductEdit}
            create={ProductCreate}
            icon={Inventory2RoundedIcon}
            options={{ label: 'Products' }}
          />
        )}
        {productsEnabled && permissions === 'admin' && (
          <Resource
            name="product-sync-runs"
            list={ProductSyncRunList}
            icon={SyncAltRoundedIcon}
            options={{ label: 'همگام‌سازی محصولات' }}
          />
        )}
        <Resource
          name="conversations"
          list={ConversationList}
          icon={ForumRoundedIcon}
          options={{ label: 'Conversations' }}
        />
        <Resource
          name="messages"
          list={MessageList}
          icon={MessageRoundedIcon}
          options={{ label: 'Messages' }}
        />
        <Resource
          name="users"
          list={UserList}
          edit={UserEdit}
          icon={PeopleAltRoundedIcon}
          options={{ label: 'Contacts' }}
        />
        {(permissions === 'admin' || permissions === 'staff') && (
          <Resource
            name="tickets"
            list={TicketList}
            edit={TicketEdit}
            icon={SupportAgentRoundedIcon}
            options={{ label: 'Support Tickets' }}
          />
        )}
        {(permissions === 'admin' || permissions === 'staff') && (
          <Resource
            name="followups"
            list={FollowupList}
            edit={FollowupEdit}
            icon={ScheduleRoundedIcon}
            options={{ label: 'Followups' }}
          />
        )}
        {permissions === 'admin' && (
          <Resource
            name="settings"
            list={SettingsList}
            edit={SettingsEdit}
            icon={SettingsRoundedIcon}
            options={{ label: 'AI Settings' }}
          />
        )}
        <Resource
          name="logs"
          list={LogList}
          icon={AnalyticsRoundedIcon}
          options={{ label: 'Logs' }}
        />
      </>
    )}
  </Admin>
);
