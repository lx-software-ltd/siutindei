import 'package:material_ui/material_ui.dart';

import 'semantic_tokens.dart';

/// Component (leaf) design tokens - the most specific level.
///
/// These tokens define the exact styling for individual components.
/// They are the "leaf" of the token hierarchy and are what widgets consume.
///
/// ## Token Hierarchy
/// ```
/// Primitive → Semantic → Component (this file - LEAF)
/// ```
///
/// ## Why Leaf Tokens?
/// - Maximum flexibility: change a button's color without affecting cards
/// - Design consistency: all buttons use the same token source
/// - Easy theming: swap entire component appearances via token overrides
///
/// ## Usage in Widgets
/// ```dart
/// class MyButton extends ConsumerWidget {
///   Widget build(context, ref) {
///     final tokens = ref.watch(componentTokensProvider);
///     return Container(
///       color: tokens.button.primaryBackground,
///       padding: tokens.button.padding,
///     );
///   }
/// }
/// ```
class ComponentTokens {
  const ComponentTokens({
    required this.button,
    required this.input,
    required this.card,
    required this.chip,
    required this.avatar,
    required this.badge,
    required this.list,
    required this.appBar,
    required this.bottomSheet,
    required this.searchBar,
    required this.activityCard,
    required this.filterChip,
    required this.priceTag,
  });

  final ButtonTokens button;
  final InputTokens input;
  final CardTokens card;
  final ChipTokens chip;
  final AvatarTokens avatar;
  final BadgeTokens badge;
  final ListTokens list;
  final AppBarTokens appBar;
  final BottomSheetTokens bottomSheet;
  final SearchBarTokens searchBar;
  final ActivityCardTokens activityCard;
  final FilterChipTokens filterChip;
  final PriceTagTokens priceTag;

  /// Create component tokens from semantic tokens.
  factory ComponentTokens.fromSemantic(SemanticTokens s) {
    return ComponentTokens(
      button: ButtonTokens.fromSemantic(s),
      input: InputTokens.fromSemantic(s),
      card: CardTokens.fromSemantic(s),
      chip: ChipTokens.fromSemantic(s),
      avatar: AvatarTokens.fromSemantic(s),
      badge: BadgeTokens.fromSemantic(s),
      list: ListTokens.fromSemantic(s),
      appBar: AppBarTokens.fromSemantic(s),
      bottomSheet: BottomSheetTokens.fromSemantic(s),
      searchBar: SearchBarTokens.fromSemantic(s),
      activityCard: ActivityCardTokens.fromSemantic(s),
      filterChip: FilterChipTokens.fromSemantic(s),
      priceTag: PriceTagTokens.fromSemantic(s),
    );
  }

  /// Create with JSON overrides.
  factory ComponentTokens.fromJson(
    Map<String, dynamic> json,
    SemanticTokens semantic,
  ) {
    final base = ComponentTokens.fromSemantic(semantic);
    // JSON overrides can be applied here per component
    return base;
  }
}

// ============================================================
// BUTTON TOKENS
// ============================================================

class ButtonTokens {
  const ButtonTokens({
    // Primary button
    required this.primaryBackground,
    required this.primaryBackgroundHover,
    required this.primaryBackgroundPressed,
    required this.primaryBackgroundDisabled,
    required this.primaryForeground,
    required this.primaryForegroundDisabled,
    // Secondary button
    required this.secondaryBackground,
    required this.secondaryBackgroundHover,
    required this.secondaryBorder,
    required this.secondaryForeground,
    // Text button
    required this.textForeground,
    required this.textForegroundHover,
    // Sizing
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.paddingHorizontalSm,
    required this.paddingVerticalSm,
    required this.borderRadius,
    required this.fontSize,
    required this.fontWeight,
  });

  // Primary
  final Color primaryBackground;
  final Color primaryBackgroundHover;
  final Color primaryBackgroundPressed;
  final Color primaryBackgroundDisabled;
  final Color primaryForeground;
  final Color primaryForegroundDisabled;

  // Secondary
  final Color secondaryBackground;
  final Color secondaryBackgroundHover;
  final Color secondaryBorder;
  final Color secondaryForeground;

  // Text
  final Color textForeground;
  final Color textForegroundHover;

  // Sizing
  final double paddingHorizontal;
  final double paddingVertical;
  final double paddingHorizontalSm;
  final double paddingVerticalSm;
  final double borderRadius;
  final double fontSize;
  final FontWeight fontWeight;

  factory ButtonTokens.fromSemantic(SemanticTokens s) {
    return ButtonTokens(
      primaryBackground: s.color.primary,
      primaryBackgroundHover: s.color.primaryHover,
      primaryBackgroundPressed: s.color.primaryPressed,
      primaryBackgroundDisabled: s.color.interactiveDisabled,
      primaryForeground: s.color.onPrimary,
      primaryForegroundDisabled: s.color.textTertiary,
      secondaryBackground: s.color.surface,
      secondaryBackgroundHover: s.color.surfaceHover,
      secondaryBorder: s.color.primary,
      secondaryForeground: s.color.primary,
      textForeground: s.color.primary,
      textForegroundHover: s.color.primaryHover,
      paddingHorizontal: s.spacing.lg,
      paddingVertical: s.spacing.md,
      paddingHorizontalSm: s.spacing.md,
      paddingVerticalSm: s.spacing.sm,
      borderRadius: s.radius.button,
      fontSize: 15,
      fontWeight: FontWeight.w600,
    );
  }
}

// ============================================================
// INPUT TOKENS
// ============================================================

class InputTokens {
  const InputTokens({
    required this.background,
    required this.backgroundFocused,
    required this.border,
    required this.borderFocused,
    required this.borderError,
    required this.text,
    required this.placeholder,
    required this.label,
    required this.icon,
    required this.iconFocused,
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.borderRadius,
    required this.borderWidth,
    required this.borderWidthFocused,
  });

  final Color background;
  final Color backgroundFocused;
  final Color border;
  final Color borderFocused;
  final Color borderError;
  final Color text;
  final Color placeholder;
  final Color label;
  final Color icon;
  final Color iconFocused;
  final double paddingHorizontal;
  final double paddingVertical;
  final double borderRadius;
  final double borderWidth;
  final double borderWidthFocused;

  factory InputTokens.fromSemantic(SemanticTokens s) {
    return InputTokens(
      background: s.color.background,
      backgroundFocused: s.color.surface,
      border: s.color.border,
      borderFocused: s.color.borderFocused,
      borderError: s.color.error,
      text: s.color.textPrimary,
      placeholder: s.color.textTertiary,
      label: s.color.textSecondary,
      icon: s.color.textTertiary,
      iconFocused: s.color.primary,
      paddingHorizontal: s.spacing.md,
      paddingVertical: s.spacing.md,
      borderRadius: s.radius.input,
      borderWidth: 1,
      borderWidthFocused: 2,
    );
  }
}

// ============================================================
// CARD TOKENS
// ============================================================

class CardTokens {
  const CardTokens({
    required this.background,
    required this.backgroundHover,
    required this.border,
    required this.borderRadius,
    required this.padding,
    required this.shadow,
    required this.gap,
  });

  final Color background;
  final Color backgroundHover;
  final Color border;
  final double borderRadius;
  final double padding;
  final List<BoxShadow> shadow;
  final double gap;

  factory CardTokens.fromSemantic(SemanticTokens s) {
    return CardTokens(
      background: s.color.surface,
      backgroundHover: s.color.surfaceHover,
      border: s.color.border,
      borderRadius: s.radius.card,
      padding: s.spacing.md,
      shadow: s.shadow.card,
      gap: s.spacing.sm,
    );
  }
}

// ============================================================
// CHIP TOKENS
// ============================================================

class ChipTokens {
  const ChipTokens({
    required this.background,
    required this.backgroundSelected,
    required this.border,
    required this.borderSelected,
    required this.text,
    required this.textSelected,
    required this.icon,
    required this.iconSelected,
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.borderRadius,
    required this.fontSize,
  });

  final Color background;
  final Color backgroundSelected;
  final Color border;
  final Color borderSelected;
  final Color text;
  final Color textSelected;
  final Color icon;
  final Color iconSelected;
  final double paddingHorizontal;
  final double paddingVertical;
  final double borderRadius;
  final double fontSize;

  factory ChipTokens.fromSemantic(SemanticTokens s) {
    return ChipTokens(
      background: s.color.background,
      backgroundSelected: s.color.primaryMuted,
      border: s.color.border,
      borderSelected: s.color.primary,
      text: s.color.textSecondary,
      textSelected: s.color.primary,
      icon: s.color.textTertiary,
      iconSelected: s.color.primary,
      paddingHorizontal: s.spacing.sm + 4,
      paddingVertical: s.spacing.sm,
      borderRadius: s.radius.chip,
      fontSize: 14,
    );
  }
}

// ============================================================
// AVATAR TOKENS
// ============================================================

class AvatarTokens {
  const AvatarTokens({
    required this.background,
    required this.foreground,
    required this.border,
    required this.sizeSm,
    required this.sizeMd,
    required this.sizeLg,
    required this.borderRadius,
    required this.fontSize,
  });

  final Color background;
  final Color foreground;
  final Color border;
  final double sizeSm;
  final double sizeMd;
  final double sizeLg;
  final double borderRadius;
  final double fontSize;

  factory AvatarTokens.fromSemantic(SemanticTokens s) {
    return AvatarTokens(
      background: s.color.primaryMuted,
      foreground: s.color.primary,
      border: s.color.border,
      sizeSm: 32,
      sizeMd: 40,
      sizeLg: 48,
      borderRadius: s.radius.md,
      fontSize: 14,
    );
  }
}

// ============================================================
// BADGE TOKENS
// ============================================================

class BadgeTokens {
  const BadgeTokens({
    required this.background,
    required this.foreground,
    required this.successBackground,
    required this.successForeground,
    required this.warningBackground,
    required this.warningForeground,
    required this.errorBackground,
    required this.errorForeground,
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.borderRadius,
    required this.fontSize,
  });

  final Color background;
  final Color foreground;
  final Color successBackground;
  final Color successForeground;
  final Color warningBackground;
  final Color warningForeground;
  final Color errorBackground;
  final Color errorForeground;
  final double paddingHorizontal;
  final double paddingVertical;
  final double borderRadius;
  final double fontSize;

  factory BadgeTokens.fromSemantic(SemanticTokens s) {
    return BadgeTokens(
      background: s.color.primaryMuted,
      foreground: s.color.primary,
      successBackground: s.color.successMuted,
      successForeground: s.color.success,
      warningBackground: s.color.warningMuted,
      warningForeground: s.color.warning,
      errorBackground: s.color.errorMuted,
      errorForeground: s.color.error,
      paddingHorizontal: s.spacing.sm,
      paddingVertical: s.spacing.xs,
      borderRadius: 4,
      fontSize: 11,
    );
  }
}

// ============================================================
// LIST TOKENS
// ============================================================

class ListTokens {
  const ListTokens({
    required this.itemBackground,
    required this.itemBackgroundHover,
    required this.itemBackgroundPressed,
    required this.divider,
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.itemGap,
  });

  final Color itemBackground;
  final Color itemBackgroundHover;
  final Color itemBackgroundPressed;
  final Color divider;
  final double paddingHorizontal;
  final double paddingVertical;
  final double itemGap;

  factory ListTokens.fromSemantic(SemanticTokens s) {
    return ListTokens(
      itemBackground: s.color.surface,
      itemBackgroundHover: s.color.surfaceHover,
      itemBackgroundPressed: s.color.surfacePressed,
      divider: s.color.border,
      paddingHorizontal: s.spacing.md,
      paddingVertical: s.spacing.sm,
      itemGap: s.spacing.xs,
    );
  }
}

// ============================================================
// APP BAR TOKENS
// ============================================================

class AppBarTokens {
  const AppBarTokens({
    required this.background,
    required this.foreground,
    required this.titleFontSize,
    required this.titleFontWeight,
    required this.iconSize,
    required this.height,
    required this.elevation,
  });

  final Color background;
  final Color foreground;
  final double titleFontSize;
  final FontWeight titleFontWeight;
  final double iconSize;
  final double height;
  final double elevation;

  factory AppBarTokens.fromSemantic(SemanticTokens s) {
    return AppBarTokens(
      background: s.color.surface,
      foreground: s.color.textPrimary,
      titleFontSize: 20,
      titleFontWeight: FontWeight.w600,
      iconSize: 24,
      height: 56,
      elevation: 0,
    );
  }
}

// ============================================================
// BOTTOM SHEET TOKENS
// ============================================================

class BottomSheetTokens {
  const BottomSheetTokens({
    required this.background,
    required this.handleColor,
    required this.handleWidth,
    required this.handleHeight,
    required this.borderRadius,
    required this.padding,
  });

  final Color background;
  final Color handleColor;
  final double handleWidth;
  final double handleHeight;
  final double borderRadius;
  final double padding;

  factory BottomSheetTokens.fromSemantic(SemanticTokens s) {
    return BottomSheetTokens(
      background: s.color.surface,
      handleColor: s.color.border,
      handleWidth: 40,
      handleHeight: 4,
      borderRadius: s.radius.sheet,
      padding: s.spacing.md,
    );
  }
}

// ============================================================
// SEARCH BAR TOKENS (App-specific)
// ============================================================

class SearchBarTokens {
  const SearchBarTokens({
    required this.background,
    required this.backgroundFocused,
    required this.border,
    required this.borderFocused,
    required this.text,
    required this.placeholder,
    required this.icon,
    required this.iconFocused,
    required this.clearIcon,
    required this.padding,
    required this.borderRadius,
    required this.height,
  });

  final Color background;
  final Color backgroundFocused;
  final Color border;
  final Color borderFocused;
  final Color text;
  final Color placeholder;
  final Color icon;
  final Color iconFocused;
  final Color clearIcon;
  final double padding;
  final double borderRadius;
  final double height;

  factory SearchBarTokens.fromSemantic(SemanticTokens s) {
    return SearchBarTokens(
      background: s.color.background,
      backgroundFocused: s.color.surface,
      border: s.color.border,
      borderFocused: s.color.borderFocused,
      text: s.color.textPrimary,
      placeholder: s.color.textTertiary,
      icon: s.color.textTertiary,
      iconFocused: s.color.primary,
      clearIcon: s.color.textTertiary,
      padding: s.spacing.md,
      borderRadius: s.radius.input,
      height: 48,
    );
  }
}

// ============================================================
// ACTIVITY CARD TOKENS (App-specific leaf tokens)
// ============================================================

class ActivityCardTokens {
  const ActivityCardTokens({
    required this.background,
    required this.backgroundHover,
    required this.border,
    required this.borderRadius,
    required this.padding,
    required this.gap,
    // Title
    required this.titleColor,
    required this.titleFontSize,
    required this.titleFontWeight,
    // Subtitle
    required this.subtitleColor,
    required this.subtitleFontSize,
    // Organization
    required this.organizationColor,
    required this.organizationFontSize,
    // Location
    required this.locationColor,
    required this.locationIconColor,
    required this.locationFontSize,
    // Schedule
    required this.scheduleColor,
    required this.scheduleIconColor,
    required this.scheduleFontSize,
    // Age badge
    required this.ageBackground,
    required this.ageForeground,
    required this.ageFontSize,
    // Avatar
    required this.avatarSize,
    required this.avatarRadius,
  });

  final Color background;
  final Color backgroundHover;
  final Color border;
  final double borderRadius;
  final double padding;
  final double gap;

  final Color titleColor;
  final double titleFontSize;
  final FontWeight titleFontWeight;

  final Color subtitleColor;
  final double subtitleFontSize;

  final Color organizationColor;
  final double organizationFontSize;

  final Color locationColor;
  final Color locationIconColor;
  final double locationFontSize;

  final Color scheduleColor;
  final Color scheduleIconColor;
  final double scheduleFontSize;

  final Color ageBackground;
  final Color ageForeground;
  final double ageFontSize;

  final double avatarSize;
  final double avatarRadius;

  factory ActivityCardTokens.fromSemantic(SemanticTokens s) {
    return ActivityCardTokens(
      background: s.color.surface,
      backgroundHover: s.color.surfaceHover,
      border: s.color.border,
      borderRadius: s.radius.card,
      padding: s.spacing.md,
      gap: s.spacing.sm,
      titleColor: s.color.textPrimary,
      titleFontSize: 16,
      titleFontWeight: FontWeight.w600,
      subtitleColor: s.color.textSecondary,
      subtitleFontSize: 13,
      organizationColor: s.color.textSecondary,
      organizationFontSize: 13,
      locationColor: s.color.textTertiary,
      locationIconColor: s.color.textTertiary,
      locationFontSize: 12,
      scheduleColor: s.color.textSecondary,
      scheduleIconColor: s.color.textSecondary,
      scheduleFontSize: 13,
      ageBackground: s.color.secondaryMuted,
      ageForeground: s.color.secondary,
      ageFontSize: 12,
      avatarSize: 40,
      avatarRadius: s.radius.md,
    );
  }
}

// ============================================================
// FILTER CHIP TOKENS (App-specific)
// ============================================================

class FilterChipTokens {
  const FilterChipTokens({
    required this.background,
    required this.backgroundSelected,
    required this.backgroundHover,
    required this.border,
    required this.borderSelected,
    required this.text,
    required this.textSelected,
    required this.dropdownIcon,
    required this.badgeBackground,
    required this.badgeForeground,
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.borderRadius,
    required this.fontSize,
    required this.fontWeight,
    required this.fontWeightSelected,
  });

  final Color background;
  final Color backgroundSelected;
  final Color backgroundHover;
  final Color border;
  final Color borderSelected;
  final Color text;
  final Color textSelected;
  final Color dropdownIcon;
  final Color badgeBackground;
  final Color badgeForeground;
  final double paddingHorizontal;
  final double paddingVertical;
  final double borderRadius;
  final double fontSize;
  final FontWeight fontWeight;
  final FontWeight fontWeightSelected;

  factory FilterChipTokens.fromSemantic(SemanticTokens s) {
    return FilterChipTokens(
      background: s.color.background,
      backgroundSelected: s.color.primaryMuted,
      backgroundHover: s.color.surfaceHover,
      border: s.color.border,
      borderSelected: s.color.primary,
      text: s.color.textSecondary,
      textSelected: s.color.primary,
      dropdownIcon: s.color.textSecondary,
      badgeBackground: s.color.primary,
      badgeForeground: s.color.onPrimary,
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: s.radius.chip,
      fontSize: 14,
      fontWeight: FontWeight.normal,
      fontWeightSelected: FontWeight.w600,
    );
  }
}

// ============================================================
// PRICE TAG TOKENS (App-specific)
// ============================================================

class PriceTagTokens {
  const PriceTagTokens({
    required this.background,
    required this.foreground,
    required this.paddingHorizontal,
    required this.paddingVertical,
    required this.borderRadius,
    required this.fontSize,
    required this.fontWeight,
  });

  final Color background;
  final Color foreground;
  final double paddingHorizontal;
  final double paddingVertical;
  final double borderRadius;
  final double fontSize;
  final FontWeight fontWeight;

  factory PriceTagTokens.fromSemantic(SemanticTokens s) {
    return PriceTagTokens(
      background: s.color.primaryMuted,
      foreground: s.color.primary,
      paddingHorizontal: 10,
      paddingVertical: 6,
      borderRadius: s.radius.chip,
      fontSize: 14,
      fontWeight: FontWeight.w600,
    );
  }
}
