---
name: digitakt-code-patterns
description: Common code patterns for Digitakt mods
slug: digitakt-code-patterns
---

# Digitakt Mod Code Patterns

Reusable C and assembly patterns for Digitakt mod development.

## Minimal Hook Handler

```c
// mod.json: {"event": "ev_draw", "handler": "mymod_on_draw"}

void mymod_on_draw(void) {
    // Called ~50 times per second to update display
    // Don't block; keep it fast
    firmware_draw_text("MY MOD", 10, 20);
}
```

## Subscribing to Multiple Events

```c
// mod.json
{
  "subscribe": [
    {"event": "ev_tick", "handler": "mymod_on_tick"},
    {"event": "ev_draw", "handler": "mymod_on_draw"},
    {"event": "ev_enc", "handler": "mymod_on_enc"}
  ]
}

// Handler signatures
void mymod_on_tick(void) {
    // Audio processing (41.666 kHz, real-time)
}

void mymod_on_draw(void) {
    // UI update (~50 Hz)
}

void mymod_on_enc(u8 encoder_id, u8 direction) {
    // Encoder rotate: direction = 1 (right) or -1 (left)
}
```

## Maintaining State Across Hooks

**Use static variables for real-time state**:

```c
static u16 mymod_phase = 0;  // Persists across ev_tick calls

void mymod_on_tick(void) {
    mymod_phase += 256;  // Increment phase accumulator
    // Use mymod_phase for waveform generation
}
```

**Use kit slots for pattern-persistent state**:

```c
// mod.json: {"resources": {"sound": {"slots": [52]}}}

struct mymod_state {
    u8 param1;
    u8 param2;
} __attribute__((packed));

void mymod_on_enc(u8 encoder_id, u8 direction) {
    struct mymod_state state;
    firmware_read_kit_slot(52, &state, sizeof(state));
    
    state.param1 += direction;
    
    firmware_write_kit_slot(52, &state, sizeof(state));
}
```

## Settings Menu Integration

```c
// mod.json
{
  "subscribe": [{"event": "ev_settings", "handler": "mymod_on_settings"}],
  "resources": {"settings": ["mymod_settings"]}
}

// Settings parameter struct
struct mymod_settings_page {
    u8 param1;
    u8 param2;
    u8 param3;
};

// Handler
void mymod_on_settings(struct settings_context *ctx) {
    // ctx->encoder_id: which encoder was moved
    // ctx->direction: +1 or -1
    // ctx->param: which parameter (0-15)
    
    struct mymod_settings_page *params = 
        (struct mymod_settings_page *)ctx->page_data;
    
    if (ctx->encoder_id == ENCODER_MAIN) {
        params->param1 = clamp(params->param1 + ctx->direction, 0, 127);
    }
    
    // Redraw
    firmware_draw_text("PARAM1:", 10, 20);
    firmware_draw_value(params->param1, 50, 20);
}
```

## Audio Buffer Processing

```c
// Real-time audio in ev_tick or ev_render_in/out

// Pre-allocate buffer (no malloc in real-time)
#define AUDIO_BUFFER_SIZE 256
static s16 mymod_buffer[AUDIO_BUFFER_SIZE];

void mymod_on_tick(void) {
    // Process audio from firmware input buffer
    const s16 *in = firmware_get_audio_input();
    s16 *out = firmware_get_audio_output();
    
    for (int i = 0; i < AUDIO_BUFFER_SIZE; i++) {
        // Apply effect
        out[i] = apply_effect(in[i]);
    }
}
```

## Firmware Function Calls

**Pattern**: Function pointers defined in core or headers.

```c
// From firmware header
typedef void (*fw_draw_text)(const char *str, u16 x, u16 y);
extern fw_draw_text firmware_draw_text;

// Usage
firmware_draw_text("HELLO", 10, 20);
```

## Avoiding Common Pitfalls

### 1. Don't Use Global Mutable State in Real-Time Hooks

**Bad**:
```c
u16 global_counter = 0;  // Can overflow, not deterministic

void mymod_on_tick(void) {
    global_counter++;  // Non-real-time safe
}
```

**Good**:
```c
static u16 phase = 0;

void mymod_on_tick(void) {
    phase += increment;  // Deterministic per sample
}
```

### 2. Don't Block or Allocate in Real-Time Hooks

**Bad**:
```c
void mymod_on_tick(void) {
    void *ptr = malloc(1024);  // Blocks!
    firmware_call_slow_function();  // Can stall audio
}
```

**Good**:
```c
static s16 buffer[1024];  // Pre-allocated

void mymod_on_tick(void) {
    // Use buffer without allocation
}
```

### 3. Use Kit Slots, Not Global Variables, for Pattern State

**Bad**:
```c
struct pattern_state {
    u8 param[16];
} global_pattern;  // Doesn't persist across pattern changes
```

**Good**:
```c
// mod.json: {"resources": {"sound": {"slots": [52, 53]}}}

void save_pattern_state(const struct pattern_state *state) {
    firmware_write_kit_slot(52, state, sizeof(*state));
}
```

### 4. Prefix Symbols to Avoid Conflicts

**Bad**:
```c
void on_draw(void) { }   // Collides with other mods
u8 state[256];           // Global namespace pollution
```

**Good**:
```c
void mymod_on_draw(void) { }  // SDK auto-prefixes to mymod_on_draw
static u8 mymod_state[256];   // Static = local scope
```

## Reference

- **Firmware addresses**: elekloader headers and tools
- **Examples**: 
  - Simple: `elekloader/examples/hello-marker/src/main.c`
  - Complex: `digi1_mods/mods/digipoly/src/`
  - Settings UI: `digi1_mods/mods/digieq/src/ui.c`

