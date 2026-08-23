<script lang="ts">
  import "../app.css";
  import favicon from "$lib/assets/favicon.svg";
  import { onMount } from "svelte";
  import { dev } from "$app/environment";
  import * as Swetrix from "swetrix";
  let { children } = $props();

  onMount(() => {
    Swetrix.init("lp61TqcIrztc", {
      devMode: dev,
      disabled: dev,
      apiURL: "https://api.analytics.jenskrumsieck.de/log",
    });
    Swetrix.trackViews();
  });
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<div class="flex h-dvh flex-col bg-grey-700">
  <div class="min-h-0 flex-1">
    {@render children()}
  </div>
  <footer
    class="p-3 sm:p-5 shrink-0 text-center container container-md mx-auto dark:text-grey-400 text-grey-600 text-xs sm:text-sm border-t dark:border-grey-600 border-grey-50"
  >
    <div class="mt-2 sm:mt-5 text-primary-200">
      Ein Projekt von <a
        class="underline font-medium"
        href="https://jenskrumsieck.de">Dr. Jens Krumsieck</a
      >.
    </div>
    <div class="mt-2 dark:text-grey-400 text-grey-600">
      <a
        class="underline"
        target="_blank"
        href="https://jenskrumsieck.de/privacy">Datenschutzerklärung</a
      >
      |
      <a
        class="underline"
        target="_blank"
        href="https://jenskrumsieck.de/impressum">Impressum</a
      >
    </div>
  </footer>
</div>
