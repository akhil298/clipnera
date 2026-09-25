import DashboardApp from '@/components/dashboard/DashboardApp';

/**
 * Mounts the dashboard shell once for every route in this group, so moving
 * between tabs keeps the sidebar, header and loaded data instead of remounting
 * the whole app. DashboardApp picks the view from the pathname; the pages here
 * only exist to register the URLs.
 */
export default function DashboardShellLayout() {
  return <DashboardApp />;
}
