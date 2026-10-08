import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../config/tokens/tokens.dart';
import '../../../core/core.dart';
import '../../../domain/entities/entities.dart';
import '../../../viewmodels/activities_viewmodel.dart';
import '../../activity_detail/screens/activity_detail_screen.dart';
import '../../search/widgets/activity_card.dart';

/// Organization detail screen using design tokens and domain entities.
///
/// Architecture:
/// - Uses domain entities (OrganizationEntity)
/// - Follows Flutter architecture guidelines
///
/// See: https://docs.flutter.dev/app-architecture/guide
class OrganizationScreen extends ConsumerWidget {
  const OrganizationScreen({super.key, required this.organization});

  final OrganizationEntity organization;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final activitiesState = ref.watch(activitiesViewModelProvider);
    final semantic = ref.watch(semanticTokensProvider);

    // Filter activities for this organization
    final orgActivities = activitiesState.items
        .where((item) => item.organization.id == organization.id)
        .toList();

    return Scaffold(
      body: CustomScrollView(
        slivers: [
          _buildAppBar(context, semantic),
          SliverToBoxAdapter(child: _buildOrganizationInfo(semantic)),
          SliverToBoxAdapter(child: _buildImageGallery(semantic)),
          SliverToBoxAdapter(
            child: _buildActivitiesHeader(orgActivities.length, semantic),
          ),
          if (orgActivities.isNotEmpty)
            SliverList(
              delegate: SliverChildBuilderDelegate((context, index) {
                final result = orgActivities[index];
                return ActivityCard(
                  result: result,
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => ActivityDetailScreen(result: result),
                    ),
                  ),
                );
              }, childCount: orgActivities.length),
            )
          else
            SliverToBoxAdapter(child: _buildNoActivitiesMessage(semantic)),
          SliverToBoxAdapter(child: SizedBox(height: semantic.spacing.xl)),
        ],
      ),
    );
  }

  Widget _buildAppBar(BuildContext context, SemanticTokens semantic) {
    return SliverAppBar(
      expandedHeight: 200,
      pinned: true,
      flexibleSpace: FlexibleSpaceBar(background: _buildHeaderImage(semantic)),
      leading: IconButton(
        onPressed: () => Navigator.pop(context),
        icon: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: semantic.color.surface.withValues(alpha: 0.9),
            shape: BoxShape.circle,
          ),
          child: Icon(Icons.arrow_back, color: semantic.color.textPrimary),
        ),
      ),
    );
  }

  Widget _buildHeaderImage(SemanticTokens semantic) {
    final imageUrl = organization.primaryMediaUrl;
    if (imageUrl != null) {
      return Image.network(
        imageUrl,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) =>
            _buildPlaceholderImage(semantic),
      );
    }
    return _buildPlaceholderImage(semantic);
  }

  Widget _buildPlaceholderImage(SemanticTokens semantic) {
    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            semantic.color.primary.withValues(alpha: 0.8),
            semantic.color.primaryPressed,
          ],
        ),
      ),
      child: Center(child: _buildInitialsAvatar(80, semantic)),
    );
  }

  Widget _buildInitialsAvatar(double size, SemanticTokens semantic) {
    final initials = organization.name.isNotEmpty
        ? organization.name
              .split(' ')
              .take(2)
              .map((e) => e.isNotEmpty ? e[0].toUpperCase() : '')
              .join()
        : '?';
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: semantic.color.onPrimary.withValues(alpha: 0.2),
        shape: BoxShape.circle,
      ),
      child: Center(
        child: Text(
          initials,
          style: TextStyle(
            fontSize: size * 0.4,
            fontWeight: FontWeight.bold,
            color: semantic.color.onPrimary,
          ),
        ),
      ),
    );
  }

  Widget _buildOrganizationInfo(SemanticTokens semantic) {
    return Padding(
      padding: EdgeInsets.all(semantic.spacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(organization.name, style: semantic.text.headlineMedium),
          if (organization.description != null) ...[
            SizedBox(height: semantic.spacing.sm),
            Text(organization.description!, style: semantic.text.bodyMedium),
          ],
          SizedBox(height: semantic.spacing.md),
          Row(
            children: [
              BaseBadge(
                label: 'Verified',
                icon: Icons.verified,
                variant: BadgeVariant.success,
              ),
              const SizedBox(width: 8),
              BaseBadge(
                label: 'Top Rated',
                icon: Icons.star,
                variant: BadgeVariant.warning,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildImageGallery(SemanticTokens semantic) {
    if (organization.mediaUrls.length <= 1) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.symmetric(horizontal: semantic.spacing.md),
          child: Text('Gallery', style: semantic.text.titleMedium),
        ),
        SizedBox(height: semantic.spacing.sm),
        SizedBox(
          height: 120,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            padding: EdgeInsets.symmetric(horizontal: semantic.spacing.md),
            itemCount: organization.mediaUrls.length,
            itemBuilder: (context, index) {
              return Padding(
                padding: EdgeInsets.only(right: semantic.spacing.sm),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(semantic.radius.md),
                  child: Image.network(
                    organization.mediaUrls[index],
                    width: 160,
                    height: 120,
                    fit: BoxFit.cover,
                    errorBuilder: (context, error, stackTrace) => Container(
                      width: 160,
                      height: 120,
                      color: semantic.color.backgroundMuted,
                      child: Icon(
                        Icons.broken_image,
                        color: semantic.color.textTertiary,
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        SizedBox(height: semantic.spacing.md),
      ],
    );
  }

  Widget _buildActivitiesHeader(int count, SemanticTokens semantic) {
    return Padding(
      padding: EdgeInsets.fromLTRB(
        semantic.spacing.md,
        semantic.spacing.md,
        semantic.spacing.md,
        semantic.spacing.sm,
      ),
      child: Row(
        children: [
          Text('Activities', style: semantic.text.titleMedium),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: semantic.color.primaryMuted,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              count.toString(),
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w600,
                color: semantic.color.primary,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNoActivitiesMessage(SemanticTokens semantic) {
    return Padding(
      padding: EdgeInsets.all(semantic.spacing.xl),
      child: Column(
        children: [
          Icon(
            Icons.calendar_today,
            size: 48,
            color: semantic.color.textTertiary.withValues(alpha: 0.5),
          ),
          SizedBox(height: semantic.spacing.md),
          Text(
            'No activities in current search',
            style: semantic.text.titleSmall,
          ),
          SizedBox(height: semantic.spacing.sm),
          Text(
            'Try adjusting your filters to see more activities '
            'from this organization',
            style: semantic.text.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
