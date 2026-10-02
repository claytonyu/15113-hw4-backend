# Prompt Log for HW4
I used the Kiro IDE, with a mix of Claude Sonnet 5 and Claude Opus 5.5 to generate the front and back-ends.

## Designing the Backend
I want to make a todo list web app that uses Canvas OAuth to sync assignments. Help me make a SPEC.md file with rough categories for specifications and a brief outline of what I should put underneath each one.

(*Note:* Changed from Canvas OAuth to PATs later in the project.)

## Coding Prompt I found Online (found in SPEC.md)
You are a senior software architect. Strictly adhere to these principles:
1. KISS (Keep It Simple, Stupid): Write straightforward, uncomplicated logic. Avoid premature optimizations or speculative "what-if" abstractions.
2. YAGNI (You Aren't Gonna Need It): Do not add extra features, utility methods, or error-handling blocks for scenarios that cannot physically happen in this scope.
3. SOLID: Ensure conceptual single responsibility per class/function.
4. Reduce cognitive complexity (aim for low cyclomatic complexity).

## Updating the Front-end after Initial Implementation
I want to make these changes:

Tasks view

Along with the main "new task" button, it should be within the lists themselves. For example, when viewing by course, there should be a new task button at the top of each course's list. Pressing this will start creating a new task, with the course already pre-filled.

Visual change: I don't want the Task editing UI to prevent anything on the left side. It should not gray out the screen and prevent clicks, and should not go on top the screen.

When there are no tasks or classes at all, can you make it display: Import from Canvas here (or similar) with a link to the canvas import page?

Also allow for bulk completion of tasks (in addition to deletion and hiding)

Canvas Import

The notification wraps to two lines and the text& padding feels off. Can you increase the left bar size, or make the padding better?

I don't want the user page to jump to a newly-kept or ignored course when clicking keep or ignore -- this is annoying. When it loads assignments, also don't force the screen to it.

When assignments are hidden, the user should be able to click a expand/collapse icon to see them. These should not be highlighted anymore though.
Syncing

Important! I don't want unconditional sync on page change. I only want syncing when things happened.

I also don't like the blue bar as it is, because it shifts the whole screen down and up quickly. Instead, can you make this popup from the bottom of the screen, and make it layer on top of other elements?

Ask any questions now before implementing. If these are large enough points, change the FRONTEND_SPEC.md to fit.