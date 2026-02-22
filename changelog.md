# PostPocket Pro Changelog

## v1.1.0 
* **Feature:** Plugin System dynamically loading external `.py` extensions natively via `importlib`.
* **Security:** Added `pyotp` 2FA validation natively locking the PRO License Settings.
* **Foundation:** Mapped `QTranslator` definitions allowing extensive future i18n linguistic scaling.
* **Feature:** Drag-and-Drop post reordering enabled in the draft list.
* **Feature:** Context Menu updated to support internal native "Duplicate Post" duplicating logic, saving API syncs.
* **Feature:** Interactive Configuration `QWizard` added on boot for initial API inputs and Theme selections.
* **Feature:** Single cohesive Settings Dialog introduced mapping Fonts, Themes, and Keys.
* **Accessibility:** Added High-Contrast Mode (Pure Black background, Bright Yellow accents) for visual clarity.
* **Accessibility:** Added Keyboard Navigation mapping (`Tab` indexing) and extensive local `setAccessibleDescription` identifiers across components.
* **Polish:** Relocated obstrusive MessageBox popups (like generic import warnings) into non-modal QStatusBar slide-in messages.

## v1.0.0
* **Feature:** Accurate X Platform (Twitter) Character Counting implemented (detects 23-char URLs, tracks Threads).
* **Feature:** Total engagement KPI cards in the Analytics view are now fully Clickable to sort the Table instantly.
* **Feature:** PyQtGraph Plot rendering exportable seamlessly to a local `.png` chart.
* **Feature:** Background 5-Minute Auto-Save intervals mapped strictly to drafting spaces to prevent accidental data loss.
* **Foundation:** Transitioned backend Database models to isolated, thread-safe asynchronous `QMutex` architectures.
* **Foundation:** Handled generic OpenAI and X Network errors with passive logs to `postpocket.log` instead of fatal GUI crashes.
* **Foundation:** Introduced macOS-inspired minimal Scrollbars with dynamic hover triggers across Dark and Light mode.
