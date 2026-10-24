/// Search Feature Module
///
/// This module contains all search-related functionality:
/// - Search screen
/// - Filter widgets
/// - Activity cards
/// - Search state management
///
/// ## Area filter
///
/// SearchScreen shows AreaFilterChips, a horizontal cascading chip bar backed
/// by geographicAreaTreeProvider (GET /v1/user/areas). The selected node is
/// stored on SearchFilters.areaId and sent as area_id on activity search.
/// The same chips appear in SearchFiltersSheet.
///
/// ## Usage
///
/// ```dart
/// import 'package:siutindei_app/features/search/search.dart';
///
/// Navigator.push(context, MaterialPageRoute(
///   builder: (_) => const SearchScreen(),
/// ));
/// ```
library;

export 'screens/search_screen.dart';
export 'widgets/activity_card.dart';
export 'widgets/filter_chip_bar.dart';
export 'widgets/search_filters_sheet.dart';
