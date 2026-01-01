import { Menu, MenuItemLink, usePermissions } from 'react-admin';
import { Divider, ListSubheader } from '@mui/material';
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded';
import ForumRoundedIcon from '@mui/icons-material/ForumRounded';
import MessageRoundedIcon from '@mui/icons-material/MessageRounded';
import QuizRoundedIcon from '@mui/icons-material/QuizRounded';
import Inventory2RoundedIcon from '@mui/icons-material/Inventory2Rounded';
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded';
import AnalyticsRoundedIcon from '@mui/icons-material/AnalyticsRounded';
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded';
import PeopleAltRoundedIcon from '@mui/icons-material/PeopleAltRounded';
import FactCheckRoundedIcon from '@mui/icons-material/FactCheckRounded';
import SendRoundedIcon from '@mui/icons-material/SendRounded';

export const AppMenu = () => {
  const { permissions } = usePermissions();

  return (
    <Menu>
      <ListSubheader component="div" disableSticky sx={{ letterSpacing: 0, fontWeight: 700 }}>
        عملیات
      </ListSubheader>
      <MenuItemLink to="/conversations" primaryText="گفتگوها" leftIcon={<ForumRoundedIcon />} />
      <MenuItemLink to="/messages" primaryText="پیام‌ها" leftIcon={<MessageRoundedIcon />} />
      <MenuItemLink to="/users" primaryText="مخاطبین" leftIcon={<PeopleAltRoundedIcon />} />
      <MenuItemLink to="/logs" primaryText="لاگ‌ها" leftIcon={<AnalyticsRoundedIcon />} />
      <MenuItemLink to="/assistant" primaryText="دستیار هوشمند" leftIcon={<AutoAwesomeRoundedIcon />} />
      <MenuItemLink to="/directam" primaryText="کنسول دایرکتم" leftIcon={<SendRoundedIcon />} />
      {permissions === 'admin' && (
        <MenuItemLink to="/assistant/actions" primaryText="تاییدیه‌ها" leftIcon={<FactCheckRoundedIcon />} />
      )}
      <Divider sx={{ my: 1 }} />

      <ListSubheader component="div" disableSticky sx={{ letterSpacing: 0, fontWeight: 700 }}>
        دانش
      </ListSubheader>
      <MenuItemLink to="/campaigns" primaryText="کمپین‌ها" leftIcon={<CampaignRoundedIcon />} />
      <MenuItemLink to="/faqs" primaryText="سوالات متداول" leftIcon={<QuizRoundedIcon />} />
      {permissions === 'admin' && (
        <MenuItemLink to="/products" primaryText="محصولات" leftIcon={<Inventory2RoundedIcon />} />
      )}

      {permissions === 'admin' && (
        <>
          <Divider sx={{ my: 1 }} />
          <ListSubheader component="div" disableSticky sx={{ letterSpacing: 0, fontWeight: 700 }}>
            سیستم
          </ListSubheader>
          <MenuItemLink to="/settings" primaryText="تنظیمات هوش مصنوعی" leftIcon={<SettingsRoundedIcon />} />
        </>
      )}
    </Menu>
  );
};
