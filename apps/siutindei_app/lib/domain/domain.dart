/// Domain layer - business logic and entities.
///
/// This layer contains the core business logic of the application.
/// It is independent of any external frameworks or data sources.
///
/// ## Structure
///
/// - **entities/**: Pure business objects
///   (ActivityEntity, OrganizationEntity, etc.)
/// - **repositories/**: Interfaces for data access (implemented in data layer)
/// - **use_cases/**: Application-specific business rules
///
/// ## Architecture Guidelines
///
/// 1. Entities should be immutable and contain no framework dependencies
/// 2. Repository interfaces define the contract, not the implementation
/// 3. Use cases orchestrate business logic and validate inputs
/// 4. All async operations return `Result<T>` for type-safe error handling
///
/// See: https://docs.flutter.dev/app-architecture/guide
library;

export 'entities/entities.dart';
export 'repositories/repositories.dart';
export 'use_cases/use_cases.dart';
