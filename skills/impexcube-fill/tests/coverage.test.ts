import { beforeEach, describe, expect, test } from 'bun:test';
import { coverage, scan } from '../src/coverage';

const page = `
  <input id="ContentPlaceHolder1_txtA" value="alpha">
  <input id="ContentPlaceHolder1_txtBlank" value="">
  <select id="ContentPlaceHolder1_ddl"><option value="">--Choose--</option><option value="X" selected>X</option></select>
  <select id="ContentPlaceHolder1_ddlEmpty"><option value="">--Choose--</option><option value="X">X</option></select>
  <input type="checkbox" id="ContentPlaceHolder1_chkOn" checked>
  <input type="checkbox" id="ContentPlaceHolder1_chkOff">
  <input type="hidden" id="ContentPlaceHolder1_hid" value="secret">
  <input type="submit" id="ContentPlaceHolder1_btnUpdate" value="Update">
  <input type="hidden" id="__VIEWSTATE" value="x">
  <input id="row_chk_0" value="row">
  <input id="ContentPlaceHolder1_gvProductExp_ctl02_txt" value="row">
  <table id="ContentPlaceHolder1_x_gvrexport"><tr><td><input id="ContentPlaceHolder1_inGrid" value="g"></td></tr></table>`;

beforeEach(() => {
  document.body.innerHTML = page;
});

describe('scan', () => {
  test('lists real controls only', () => {
    expect(scan().map((c) => c.id)).toEqual([
      'ContentPlaceHolder1_txtA',
      'ContentPlaceHolder1_txtBlank',
      'ContentPlaceHolder1_ddl',
      'ContentPlaceHolder1_ddlEmpty',
      'ContentPlaceHolder1_chkOn',
      'ContentPlaceHolder1_chkOff',
    ]);
  });

  test('knows which controls hold a value', () => {
    const filled = scan()
      .filter((c) => c.filled)
      .map((c) => c.id);
    expect(filled).toEqual([
      'ContentPlaceHolder1_txtA',
      'ContentPlaceHolder1_ddl',
      'ContentPlaceHolder1_chkOn',
    ]);
  });
});

describe('coverage', () => {
  test('counts filled controls that were not compared, and every control that is in no known list', () => {
    const seen = coverage(new Set(['ContentPlaceHolder1_txtA']), new Set(['ddlEmpty']));
    expect(seen.total).toBe(6);
    expect(seen.compared).toBe(1);
    expect(seen.notCompared.map((c) => c.id)).toEqual([
      'ContentPlaceHolder1_ddl',
      'ContentPlaceHolder1_chkOn',
    ]);
    expect(seen.unknown?.map((c) => c.id)).toEqual([
      'ContentPlaceHolder1_txtBlank',
      'ContentPlaceHolder1_ddl',
      'ContentPlaceHolder1_chkOn',
      'ContentPlaceHolder1_chkOff',
    ]);
  });

  test('says nothing about new controls when no known list is given', () => {
    expect(coverage(new Set(), undefined).unknown).toBeNull();
  });
});
