# Features (Presentation Layer)

Features are self-contained UI modules that combine screens, widgets, and feature-specific logic. They represent the presentation layer of the application.

## Overview

Each feature module contains:
- **Screens**: Full-page UI components
- **Widgets**: Feature-specific UI components
- **Barrel file**: Exports for the feature

## Location

```
lib/features/
├── features.dart           # Master barrel file
├── search/                 # Activity search feature
│   ├── search.dart
│   ├── screens/
│   │   └── search_screen.dart
│   ├── utils/
│   │   └── area_filter_options.dart
│   └── widgets/
│       ├── activity_card.dart
│       ├── area_filter_chips.dart
│       ├── filter_chip_bar.dart
│       └── search_filters_sheet.dart
├── home_wizard/            # Guided home search
│   ├── home_wizard_viewmodel.dart
│   ├── models/
│   │   └── home_wizard_choices.dart
│   └── screens/
│       └── home_wizard_screen.dart
├── activity_detail/        # Activity detail feature
│   ├── activity_detail.dart
│   └── screens/
│       └── activity_detail_screen.dart
├── organization/           # Organization feature
│   ├── organization.dart
│   └── screens/
│       └── organization_screen.dart
└── auth/                   # Authentication feature
    ├── auth.dart
    └── screens/
        └── login_screen.dart
```

## Feature Structure

### Barrel File Pattern

Each feature has a barrel file that exports its public API:

```dart
// lib/features/search/search.dart
library;

// Screens
export 'screens/search_screen.dart';

// Widgets (if needed externally)
export 'widgets/activity_card.dart';
```

### Screen Structure

Screens are full-page widgets that:
- Compose feature widgets
- Connect to ViewModels via Riverpod
- Handle navigation
- Manage local UI state

```dart
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _performSearch());
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Watch state with selectors for granular rebuilds
    final isLoading = ref.watch(
      activitiesViewModelProvider.select((s) => s.isLoading),
    );

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _SearchHeader(...),
            _SearchBar(...),
            Expanded(child: _ResultsList(...)),
          ],
        ),
      ),
    );
  }
}
```

## Search Feature

### SearchScreen

Main screen for activity search with:
- Search bar
- Quick filter chips
- Advanced filters sheet
- Paginated results list

**Key Components:**
- `_SearchHeader` - Title and auth button
- `_SearchBar` - Text input with clear button
- `_QuickFilters` - Horizontal filter chip rows
- `_ResultsList` - Paginated activity list

### ActivityCard

Displays activity search results:

```dart
class ActivityCard extends ConsumerWidget {
  const ActivityCard({
    super.key,
    required this.result,
    this.onTap,
    this.onOrganizationTap,
  });

  final ActivitySearchResultEntity result;
  final VoidCallback? onTap;
  final VoidCallback? onOrganizationTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Uses component tokens for styling
    final tokens = ref.watch(
      componentTokensProvider.select((t) => t.activityCard),
    );
    // ...
  }
}
```

### FilterChipBar

Horizontal scrolling filter chips:

```dart
class FilterChipBar extends StatelessWidget {
  const FilterChipBar({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(children: children),
    );
  }
}
```

### SearchFiltersSheet

Modal bottom sheet for advanced filters:

```dart
class SearchFiltersSheet extends ConsumerStatefulWidget {
  static Future<void> show({
    required BuildContext context,
    required SearchFilters initialFilters,
    required ValueChanged<SearchFilters> onApply,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (context) => SearchFiltersSheet(
        initialFilters: initialFilters,
        onApply: onApply,
      ),
    );
  }
}
```

## Activity Detail Feature

### ActivityDetailScreen

Full activity information with:
- Hero image/gradient header
- Activity name and age range
- Organization card (tappable)
- Schedule section
- Pricing section
- Location section
- Description
- Languages
- Bottom bar with price and book button

## Organization Feature

### OrganizationScreen

Organization profile with:
- Cover image/gradient
- Organization info
- Image gallery (if multiple pictures)
- List of activities from search results

## Auth Feature

### LoginScreen

Authentication UI with:
- Email/phone input
- Sign in options (email OTP, Google, Apple)
- Social login buttons

## Performance Patterns

All feature screens follow these patterns:

### 1. Granular State Selection

```dart
// Watch only needed state slice
final items = ref.watch(
  activitiesViewModelProvider.select((s) => s.items),
);
```

### 2. Widget Extraction

```dart
// Extract to separate widget class
class _SearchHeader extends ConsumerWidget {
  // Isolated rebuild scope
}
```

### 3. RepaintBoundary

```dart
// Wrap expensive static content
RepaintBoundary(
  child: Column(
    children: [
      Text('Static Title'),
      Text('Static Subtitle'),
    ],
  ),
)
```

### 4. Const Constructors

```dart
// Use const where possible
const SizedBox(height: 8),
const Icon(Icons.search),
```

### 5. ValueKey for Lists

```dart
ListView.builder(
  itemBuilder: (context, index) {
    final item = items[index];
    return ActivityCard(
      key: ValueKey(item.id), // Stable key
      result: item,
    );
  },
)
```

## Navigation

Features handle navigation through callback props and Navigator:

```dart
// From parent to child
Navigator.push(
  context,
  MaterialPageRoute(
    builder: (_) => ActivityDetailScreen(result: result),
  ),
);

// Back navigation
Navigator.pop(context);
```

## Creating New Features

1. **Create feature directory**:
   ```
   lib/features/my_feature/
   ├── my_feature.dart
   ├── screens/
   │   └── my_screen.dart
   └── widgets/
       └── my_widget.dart
   ```

2. **Create barrel file**:
   ```dart
   // lib/features/my_feature/my_feature.dart
   library;
   export 'screens/my_screen.dart';
   ```

3. **Export from features.dart**:
   ```dart
   export 'my_feature/my_feature.dart';
   ```

4. **Create screen**:
   ```dart
   class MyScreen extends ConsumerWidget {
     const MyScreen({super.key});

     @override
     Widget build(BuildContext context, WidgetRef ref) {
       final tokens = ref.watch(semanticTokensProvider);
       // ...
     }
   }
   ```

## Testing Features

```dart
void main() {
  group('SearchScreen', () {
    testWidgets('displays search bar', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(home: SearchScreen()),
        ),
      );

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Search activities, organizations...'), findsOneWidget);
    });

    testWidgets('shows loading indicator while searching', (tester) async {
      final container = ProviderContainer(
        overrides: [
          activitiesViewModelProvider.overrideWith(
            (ref) => ActivitiesViewModel(...)..state = ActivitiesState(isLoading: true),
          ),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(home: SearchScreen()),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });
  });
}
```

## Related

- [ViewModels](../viewmodels/README.md) - State management
- [Base Widgets](../core/widgets.md) - Shared UI components
- [Design Tokens](../design/tokens.md) - Styling system
