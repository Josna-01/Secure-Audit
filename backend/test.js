try {
  const res = await fetch('http://localhost:8000/evidence/upload', {
    method: 'POST',
    body: new FormData()
  });
  console.log(await res.text());
} catch (e) { console.log(e) }
