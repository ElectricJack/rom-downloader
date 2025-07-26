# ROM Name Handling Refactoring Plan

## Problem Statement

The current codebase has inconsistent ROM name handling that leads to matching failures and edge cases, particularly with different file extensions (.zip online vs .xiso.iso locally). The root issue is that ROM operations happen in multiple "spaces" - sometimes with extensions, sometimes without, sometimes with different normalization strategies.

## Core Principle: Unified Normalized Space

**All ROM operations should happen in a consistent "normalized space" where:**
- Extensions are always removed using the same method
- Names are consistently normalized using the same rules
- Comparisons, storage, and retrieval all use this normalized form
- Display and file operations derive from this normalized form

## Current Inconsistencies Identified

### 1. Extension Removal Inconsistencies
- **RomInfo**: Uses `RomUtils.get_all_rom_extensions()` with hardcoded fallback
- **Installation Manager**: Manual extension stripping (`'.'.join(stem.split('.')[:-1])`)
- **Game Library Processor**: Uses `RomUtils.get_rom_stem()` correctly
- **ROM Model**: Duplicates extension removal logic

### 2. Normalization Strategy Confusion
- **Filtering**: Uses `normalize_rom_name(clean_name)` - normalizing already-processed name
- **Installation**: Uses `precise_normalize_rom_name()` on stems
- **Game Keys**: Generated from `clean_name` instead of original filename

### 3. Input Field Inconsistency
- Some functions expect `filename` (with extension)
- Others expect `clean_name` (without extension)
- Different parts of the system work on different representations

### 4. Multiple Sources of Truth
- `filename` field stores original name with extension
- `clean_name` field stores display name without extension
- `_installed_filename` stores actual installed filename
- Game keys derived from various combinations of the above

## Refactoring Strategy

### Phase 1: Establish Normalized Space Foundation

#### 1.1 Standardize Extension Removal
**Goal**: All extension removal goes through a single method

**Changes Required**:
```python
# In src/utils/rom_utils.py - Make this the ONLY way to remove extensions
def get_normalized_stem(self, filename: str) -> str:
    """Get normalized stem - the canonical form for all ROM operations"""
    # Remove extension using comprehensive extension list
    stem = self.get_rom_stem(filename)
    # Apply consistent normalization
    return self.normalize_rom_name(stem)

# Remove these duplicate methods:
# - clean_rom_name_for_display() 
# - Manual extension stripping in installation_status_manager.py
# - _generate_clean_name() in ROM model
```

**Files to Update**:
- `src/scraper/web_scraper.py:49-70` - Use `get_normalized_stem()`
- `src/gui/managers/installation_status_manager.py:141-143` - Replace manual stripping
- `src/models/game_library.py:34-62` - Remove `_generate_clean_name()` method
- `src/rom_manager/rom_filter.py:477` - Use `get_normalized_stem()`

#### 1.2 Unify Normalization Strategy
**Goal**: Single normalization function for all ROM identification

**Changes Required**:
```python
# In src/utils/rom_utils.py
def get_canonical_rom_name(self, filename: str) -> str:
    """Get the canonical ROM name - the key for all operations"""
    stem = self.get_rom_stem(filename)
    return self.normalize_rom_name(stem)

# This becomes the ONLY method used for:
# - Game key generation
# - ROM matching
# - Deduplication
# - Storage keys
```

**Files to Update**:
- `src/processors/game_library_processor.py:245-269` - Update `create_game_key()`
- `src/rom_manager/rom_filter.py:51-52` - Use canonical name consistently

### Phase 2: Restructure Data Models

#### 2.1 ROM Model Simplification
**Goal**: Single source of truth for ROM identity

**Current Model Issues**:
```python
@dataclass
class ROM:
    filename: str                    # Original filename with extension
    clean_name: str                  # Display name without extension  
    _installed_filename: Optional[str]  # Actual installed filename
    # Multiple representations of the same thing!
```

**Proposed Model**:
```python
@dataclass
class ROM:
    canonical_name: str              # Normalized name - the primary key
    original_filename: str           # Original filename for reference
    display_name: str               # Pretty name for UI (derived from canonical)
    _installed_filename: Optional[str]  # Actual installed filename
    
    @property
    def filename(self) -> str:
        """For backward compatibility"""
        return self.original_filename
    
    @property
    def clean_name(self) -> str:
        """For backward compatibility"""
        return self.display_name
```

**Benefits**:
- `canonical_name` is always the normalized, extension-free identifier
- All operations use `canonical_name` for consistency
- Display and file operations derive from canonical form
- Backward compatibility maintained

#### 2.2 Game Model Updates
**Goal**: Games identified by canonical ROM names

**Changes Required**:
```python
@dataclass
class Game:
    key: str                        # Generated from canonical ROM name
    canonical_names: Set[str]       # All canonical names for this game
    display_name: str              # Pretty name for UI
    
    def add_variant(self, rom: ROM):
        self.canonical_names.add(rom.canonical_name)
        # Update display name if needed
```

### Phase 3: Update Processing Pipeline

#### 3.1 ROM Creation Pipeline
**Goal**: Canonical names assigned at creation time

**Current Flow**:
```
RomInfo(filename) → clean_name via _clean_name() → ROM creation → game_key from clean_name
```

**Proposed Flow**:
```
RomInfo(filename) → canonical_name via get_canonical_rom_name() → ROM creation → game_key from canonical_name
```

**Changes Required**:
```python
# In src/scraper/web_scraper.py
class RomInfo:
    def __init__(self, name: str, url: str, size: str = "", file_type: str = "", is_folder: bool = False):
        self.original_filename = unquote(name)
        self.canonical_name = self._get_canonical_name()  # New!
        self.display_name = self._get_display_name()      # Derived from canonical
        
    def _get_canonical_name(self) -> str:
        rom_utils = get_rom_utils()
        return rom_utils.get_canonical_rom_name(self.original_filename)
```

#### 3.2 Game Key Generation
**Goal**: All game keys from canonical names

**Changes Required**:
```python
# In src/processors/game_library_processor.py
def create_game_key(self, canonical_name: str) -> str:
    """Create game key from canonical ROM name"""
    # canonical_name is already normalized and extension-free
    key = canonical_name.lower()
    # Apply additional game-level transformations
    key = re.sub(r'[^\w\s]', '', key)
    key = re.sub(r'\s+', '_', key)
    return key.strip('_')

# Usage:
game_key = self.create_game_key(rom.canonical_name)  # Not rom.clean_name!
```

### Phase 4: Update Matching and Storage

#### 4.1 ROM Matching Unification
**Goal**: All matching uses canonical names

**Changes Required**:
```python
# In src/rom_manager/rom_filter.py
def scan_existing_roms(self, target_directory: Path) -> Set[str]:
    """Returns set of canonical ROM names found on disk"""
    canonical_names = set()
    
    for entry in target_directory.iterdir():
        if self.rom_utils.is_rom_file(entry.name):
            canonical_name = self.rom_utils.get_canonical_rom_name(entry.name)
            canonical_names.add(canonical_name)
            
    return canonical_names

def is_rom_installed(self, rom: ROM, target_directory: Path) -> bool:
    """Check if ROM is installed using canonical name"""
    existing_roms = self.scan_existing_roms(target_directory)
    return rom.canonical_name in existing_roms
```

#### 4.2 Installation Status Simplification
**Goal**: Installation checking uses canonical space

**Changes Required**:
```python
# In src/gui/managers/installation_status_manager.py
def _precise_rom_match_with_filename(self, rom: ROM, existing_canonical_names: Set[str]) -> tuple[bool, Optional[str]]:
    """Match ROM using canonical name only"""
    if rom.canonical_name in existing_canonical_names:
        # Find actual filename from canonical name
        actual_filename = self._canonical_to_actual.get(rom.canonical_name)
        return True, actual_filename
    return False, None
```

### Phase 5: State and Persistence Updates

#### 5.1 State Manager Updates
**Goal**: Serialize/deserialize using canonical names

**Changes Required**:
```python
# In src/state/distributed_state_manager.py
def _serialize_rom(self, rom: ROM) -> Dict[str, Any]:
    """Serialize ROM with canonical name as primary key"""
    rom_dict = {
        'canonical_name': rom.canonical_name,
        'original_filename': rom.original_filename,
        'display_name': rom.display_name,
        # ... other fields
    }
    return rom_dict

def _deserialize_rom(self, rom_data: Dict[str, Any]) -> ROM:
    """Deserialize ROM ensuring canonical name is set"""
    return ROM(
        canonical_name=rom_data['canonical_name'],
        original_filename=rom_data['original_filename'],
        display_name=rom_data['display_name'],
        # ... other fields
    )
```

## Implementation Priority

### High Priority (Core Issues)
1. **Standardize extension removal** - Fixes .xiso.iso issues immediately
2. **Unify game key generation** - Ensures consistent game identification
3. **Fix ROM matching** - Resolves installation detection problems

### Medium Priority (Consistency)
4. **Update data models** - Cleaner architecture
5. **Simplify processing pipeline** - Reduces code duplication

### Low Priority (Optimization)
6. **State management updates** - Backward compatibility and performance

## Benefits of This Approach

### 1. Eliminates Edge Cases
- No more .zip vs .xiso.iso confusion
- Compound extensions handled consistently
- No hardcoded extension lists needed

### 2. Reduces Code Duplication
- Single extension removal method
- Single normalization strategy
- Single source of truth for ROM identity

### 3. Improves Maintainability
- Clear separation of concerns
- Predictable behavior
- Easier testing and debugging

### 4. Better Performance
- Consistent caching keys
- Reduced string processing
- Fewer comparison operations

## Migration Strategy

### Backward Compatibility
During transition, maintain compatibility:
```python
# In ROM model
@property
def clean_name(self) -> str:
    """Legacy property for backward compatibility"""
    return self.display_name

@property  
def filename(self) -> str:
    """Legacy property for backward compatibility"""
    return self.original_filename
```

### Testing Strategy
1. **Unit tests** for all normalization functions
2. **Integration tests** for ROM matching scenarios
3. **Regression tests** for existing functionality
4. **Performance tests** for large ROM collections

### Rollout Plan
1. **Phase 1**: Update utilities and fix immediate issues
2. **Phase 2**: Update data models with compatibility layer
3. **Phase 3**: Update processing pipeline
4. **Phase 4**: Update matching and storage
5. **Phase 5**: Remove compatibility layer

## Conclusion

This refactoring establishes a "normalized space" where all ROM operations happen consistently. By ensuring all comparisons, storage, and processing use the same canonical representation, we eliminate the extension-related edge cases and create a more maintainable, predictable system.

The key insight is that **ROMs should be identified by what they are (the game), not how they're packaged (the file format)**. This refactoring makes that principle concrete in the codebase.