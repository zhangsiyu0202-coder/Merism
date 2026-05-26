/**
 * Global ambient types.
 *
 * React 19 + TypeScript 5.9 dropped the legacy ``global JSX`` ambient
 * namespace in favour of the per-runtime ``React.JSX`` type. We alias
 * it back at the global level so existing ``: JSX.Element`` return
 * type annotations continue to work without touching 30+ files.
 *
 * This is the single approved exception to "no ambient globals".
 */

import type React from "react";

declare global {
  namespace JSX {
    type Element = React.JSX.Element;
    type ElementClass = React.JSX.ElementClass;
    type ElementAttributesProperty = React.JSX.ElementAttributesProperty;
    type ElementChildrenAttribute = React.JSX.ElementChildrenAttribute;
    type LibraryManagedAttributes<C, P> = React.JSX.LibraryManagedAttributes<
      C,
      P
    >;
    type IntrinsicAttributes = React.JSX.IntrinsicAttributes;
    type IntrinsicClassAttributes<T> = React.JSX.IntrinsicClassAttributes<T>;
    type IntrinsicElements = React.JSX.IntrinsicElements;
  }
}

export {};
