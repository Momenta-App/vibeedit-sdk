(() => {
  const requested = new URLSearchParams(location.search).get("text");
  if (!requested) return;
  const apply = (config) => {
    if (!config || typeof config !== "object" || (!config.slug && !config.family)) return config;
    const words = requested.trim().split(/\s+/).filter(Boolean);
    const distribute = (layers) => {
      if (!Array.isArray(layers) || !layers.length) return;
      const explicit = requested.split(/\s*[|\n]\s*/).filter(Boolean);
      const values = explicit.length === layers.length
        ? explicit
        : layers.map((_, index) => index === layers.length - 1
          ? words.slice(Math.floor(index * words.length / layers.length)).join(" ")
          : words.slice(Math.floor(index * words.length / layers.length), Math.floor((index + 1) * words.length / layers.length)).join(" "));
      layers.forEach((layer, index) => {
        if (layer && typeof layer === "object" && values[index]) layer.text = values[index];
      });
    };
    config.text = requested;
    distribute(config.text_lines);
    const recipes = [config.recipe, config.componentRecipe].filter((value) => value && typeof value === "object");
    recipes.forEach((recipe) => {
      recipe.text = requested;
      distribute(recipe.lines);
      distribute(recipe.layers);
      distribute(recipe.texts);
      distribute(recipe.crossing_texts);
    });
    return config;
  };
  const parse = JSON.parse.bind(JSON);
  JSON.parse = (value, reviver) => apply(parse(value, reviver));
  const fetchRequest = fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await fetchRequest(...args);
    const read = response.json.bind(response);
    response.json = async () => apply(await read());
    return response;
  };
})();
